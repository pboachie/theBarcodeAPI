import asyncio
import gc
import signal
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_limiter import FastAPILimiter
from pydantic import ValidationError
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

import logging
from app.api import barcode, usage, health, token, admin, bulk as bulk_api_router
from app.config import settings
from app.barcode_generator import BarcodeGenerationError
from app.mcp_server import generate_barcode_mcp
from mcp.server.fastmcp import FastMCP
from app.database import close_db_connection, init_db, get_db
from app.redis import redis_manager, close_redis_connection, initialize_redis_manager
from app.schemas import SecurityScheme

log_directory = settings.LOG_DIRECTORY
if not os.path.isabs(log_directory):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_directory = os.path.join(base_dir, log_directory)

# Ensure log directory exists with proper permissions
try:
    os.makedirs(log_directory, exist_ok=True)
    # Test write permissions
    test_file = os.path.join(log_directory, "test_write.tmp")
    with open(test_file, 'w') as f:
        f.write("test")
    os.remove(test_file)

    log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_directory, "app.log"), mode="a"),
            logging.StreamHandler()
        ]
    )
except (OSError, PermissionError) as e:
    print(f"Warning: Cannot write to log directory {log_directory}: {e}")
    print("Falling back to console-only logging")

    log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

logger = logging.getLogger(__name__)

class CustomServerHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["server"] = f"BarcodeAPI/{settings.API_VERSION}"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for handling startup/shutdown and signals"""

    current_process = os.getpid()
    logger.info(f"Lifespan starting in process {current_process}")

    shutdown_event = asyncio.Event()

    def signal_handler():
        """Handle shutdown signals"""
        logger.info("Received shutdown signal...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        logger.info(f"Initializing in process {current_process}")
        try:

            await initialize_redis_manager()
            app.state.redis_manager = redis_manager

            # Initialize background_tasks early to avoid AttributeError during shutdown
            app.state.background_tasks = []

            app.state.batch_processor = redis_manager.batch_processor
            logger.info("Verifying Redis manager state...")
            if not redis_manager.batch_processor:
                raise RuntimeError("Batch processor not initialized")

            for priority, processor in redis_manager.batch_processor.processors.items():
                if not processor.running:
                    logger.error(f"{priority} processor not running")
                    raise RuntimeError(f"{priority} processor failed to start")
                logger.debug(f"{priority} processor running")

            logger.info("Initializing database...")
            await init_db()

            logger.info("Initializing FastMCP server...")
            try:
                logger.debug("Creating FastMCP instance...")
                mcp_instance = FastMCP(
                    name="theBarcodeGeneratorMCP",
                    instructions="This server provides barcode generation capabilities. Use the generate_barcode tool to create barcodes in various formats.",
                    lifespan=app.lifespan,
                    tags=["barcode", "mcp", "barcode generator", "barcode api", "barcode mcp", "barcode generation"]
                )
                logger.debug("FastMCP instance created successfully")

                logger.debug("Adding tool to MCP instance...")
                mcp_instance.add_tool(generate_barcode_mcp, name="generate_barcode")
                logger.debug("Tool added successfully")

                logger.debug("Storing MCP instance in app.state...")
                app.state.mcp_instance = mcp_instance
                logger.info("FastMCP server initialized and stored in app.state.")

                mount_mcp_sse_app()

            except Exception as mcp_error:
                logger.error(f"Failed to initialize MCP components: {mcp_error}", exc_info=True)
                app.state.mcp_instance = None

            logger.info("Initializing rate limiter...")
            await FastAPILimiter.init(redis_manager.redis)

            logger.info("Syncing username mappings...")
            async for db in get_db():
                await redis_manager.sync_all_username_mappings(db)
                break

            logger.info("Starting background tasks...")
            app.state.background_tasks = [
                asyncio.create_task(log_memory_usage()),
                asyncio.create_task(log_pool_status())
            ]

            logger.info("Startup complete!")
            yield

            await shutdown_event.wait()

        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            raise

        finally:
            logger.info("Starting shutdown process...")
            try:
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.remove_signal_handler(sig)

                logger.info("Canceling background tasks...")
                background_tasks = getattr(app.state, 'background_tasks', [])
                for task in background_tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                logger.info("Stopping batch processors...")
                for priority, processor in redis_manager.batch_processor.processors.items():
                    logger.info(f"Stopping {priority} priority batch processor...")
                    await processor.stop()

                logger.info("Syncing data to database...")
                async for db in get_db():
                    await redis_manager.sync_redis_to_db(db)
                    break

                logger.info("Stopping services...")
                await redis_manager.stop()
                await close_redis_connection()
                await close_db_connection()

            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
                raise
            finally:
                gc.collect()
                logger.info("Shutdown complete")

    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": SecurityScheme().model_dump()
    }

    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"bearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app = FastAPI(
    debug=settings.ENVIRONMENT == "development",
    title="the Barcode API",
    description="""
    The Barcode API with MCP support allows you to generate various types of barcodes programmatically.
    Rate limits apply based on authentication status and tier level.
    """,
    version=settings.API_VERSION,
    docs_url="/swagger",
    redoc_url="/",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
    servers=[{"url": settings.SERVER_URL}],
    contact={
        "name": "the Barcode API Support",
        "url": "https://thebarcodeapi.com/support",
        "email": "support@boachiefamily.net",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://thebarcodeapi.com/tos",
    }
)

app.openapi = custom_openapi

app.state.cors_origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://thebarcodeapi.com",
    "https://api.thebarcodeapi.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=app.state.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset"
    ],
    max_age=3600
)

app.add_middleware(CustomServerHeaderMiddleware)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

async def log_pool_status():
    while True:
        try:
            pool = redis_manager.redis.connection_pool
            in_use = len(pool._available_connections)
            available = pool.max_connections - in_use
            logger.info(f"Redis Pool Status - Max Connections: {pool.max_connections}, In Use: {in_use}, Available: {available}")
        except Exception as e:
            logger.error(f"Error logging pool status: {e}")
        await asyncio.sleep(60)

async def log_memory_usage():
    while True:
        gc.collect()
        logger.debug(f"Garbage collection: {gc.get_count()}")
        await asyncio.sleep(60)

@app.get("/docs", include_in_schema=False)
async def redirect_docs_to_root():
    return RedirectResponse(url="/", status_code=301)

app.include_router(health.router)
app.include_router(barcode.router)
app.include_router(usage.router)
app.include_router(token.router)
app.include_router(admin.router)
app.include_router(bulk_api_router.router)

def mount_mcp_sse_app():
    """Mount the FastMCP SSE app after startup to ensure mcp_instance is available."""
    try:
        logger.info("Attempting to mount FastMCP SSE app.")
        if not hasattr(app.state, 'mcp_instance') or app.state.mcp_instance is None:
            logger.error("MCP instance (app.state.mcp_instance) not found. Cannot mount SSE app.")
            return

        # Mount the HTTP endpoint
        app.mount("/mcp", app.state.mcp_instance.http_app(), name="mcp_http_endpoint")
        logger.info(f"FastMCP HTTP app mounted at /mcp (full path: {settings.ROOT_PATH}/mcp)")

        # Mount the SSE endpoint
        app.mount("/mcp/sse", app.state.mcp_instance.http_app(transport="sse"), name="mcp_sse_endpoint")
        logger.info(f"FastMCP SSE app mounted at /mcp/sse (full path: {settings.ROOT_PATH}/mcp/sse)")

        # Log the available routes for debugging
        for route in app.routes:
            logger.debug(f"Available route: {route}")

    except Exception as e:
        logger.error(f"Failed to mount FastMCP apps: {e}", exc_info=True)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred. Please try again later.",
            "error_type": "InternalServerError"
        }
    )

@app.exception_handler(BarcodeGenerationError)
async def barcode_generation_exception_handler(exc: BarcodeGenerationError):
    logger.error(f"Barcode generation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"message": exc.message, "error_type": exc.error_type}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    error_messages = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=400,
        content={"message": error_messages[0], "error_type": "ValidationError"}
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(exc: ValidationError):
    logger.error(f"Pydantic validation error: {exc}")
    error_messages = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=400,
        content={"message": error_messages[0], "error_type": "ValidationError"}
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        redis_stats = await app.state.redis_manager.get_connection_stats()
        logger.debug(f"Redis Stats - Total Connections: {redis_stats.total_connections}, In Use: {redis_stats.in_use_connections}")
        return response
    except Exception as ex:
        logger.error(f"Error processing request: {ex}", exc_info=True)
        raise

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")

    if origin in app.state.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"

    return response

async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)

    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value

    return response



