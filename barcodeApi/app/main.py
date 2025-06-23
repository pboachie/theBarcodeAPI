# app/main.py

import asyncio
import gc
import os
import logging
import asyncio
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


from app.api import barcode, usage, health, token, admin, bulk as bulk_api_router
from app.config import settings
from app.barcode_generator import BarcodeGenerationError
from app.mcp_server import global_mcp_instance
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


# Debug: Check if tool is in the MCP instance
try:
    # Try to access internal tool registry
    if hasattr(global_mcp_instance, '_mcp_server'):
        server = global_mcp_instance._mcp_server
        logger.info(f"MCP server: {server}")

        # Check various attributes that might contain tools
        server_attrs = [attr for attr in dir(server) if 'tool' in attr.lower()]
        logger.info(f"Server tool-related attributes: {server_attrs}")

    else:
        logger.warning("_mcp_server attribute not found")

    # Try to access the tool manager
    if hasattr(global_mcp_instance, '_tool_manager'):
        tool_manager = global_mcp_instance._tool_manager
        logger.info(f"Tool manager: {tool_manager}")

        # Check tool manager attributes
        tm_attrs = [attr for attr in dir(tool_manager) if not attr.startswith('_')]
        logger.info(f"Tool manager public methods: {tm_attrs}")

        if hasattr(tool_manager, '_tools'):
            logger.info(f"Tool manager tools: {list(tool_manager._tools.keys()) if tool_manager._tools else 'Empty'}")

    # Check get_tools method
    try:
        tools = global_mcp_instance.get_tools()
        logger.info(f"global_mcp_instance.get_tools() result: {tools}")
        # get_tools() might be a coroutine, so let's just check the type
        logger.info(f"Tools type: {type(tools)}")
    except Exception as e:
        logger.error(f"Error calling get_tools: {e}")

    # List all FastMCP instance attributes
    logger.info(f"FastMCP instance attributes: {[attr for attr in dir(global_mcp_instance) if not attr.startswith('__')]}")

except Exception as e:
    logger.error(f"Error checking tool registry: {e}", exc_info=True)

# Global MCP instance created at module level for proper ASGI integration

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

# Create proper combined lifespan for FastAPI + FastMCP integration
@asynccontextmanager
async def integrated_lifespan(app: FastAPI):
    """Integrated lifespan that properly combines FastAPI and FastMCP"""
    # Store the MCP instance in app state
    app.state.mcp_instance = global_mcp_instance

    # Create MCP apps
    mcp_http_app = global_mcp_instance.http_app(path='/mcp')
    mcp_sse_app = global_mcp_instance.http_app(transport="sse", path='/sse')

    # Start the MCP app lifespan first
    async with mcp_http_app.lifespan(app):
        # Then run our FastAPI startup logic
        try:
            logger.info("Starting FastAPI initialization...")

            # Initialize Redis and other services
            await initialize_redis_manager()
            app.state.redis_manager = redis_manager
            app.state.background_tasks = []
            app.state.batch_processor = redis_manager.batch_processor

            # Verify Redis manager state
            logger.info("Verifying Redis manager state...")
            if not redis_manager.batch_processor:
                raise RuntimeError("Batch processor not initialized")

            for priority, processor in redis_manager.batch_processor.processors.items():
                if not processor.running:
                    logger.error(f"{priority} processor not running")
                    raise RuntimeError(f"{priority} processor failed to start")
                logger.debug(f"{priority} processor running")

            # Initialize database
            logger.info("Initializing database...")
            await init_db()

            # Initialize rate limiter
            logger.info("Initializing rate limiter...")
            await FastAPILimiter.init(redis_manager.redis)

            # Initialize database data
            logger.info("Syncing username mappings...")
            async for db in get_db():
                await redis_manager.sync_all_username_mappings(db)
                break

            logger.info("Starting background tasks...")
            app.state.background_tasks = [
                asyncio.create_task(log_memory_usage()),
                asyncio.create_task(log_pool_status())
            ]

            # Mount MCP apps after both lifecycles are started
            logger.info("Creating MCP HTTP and SSE apps...")
            logger.info(f"Global MCP instance before mounting: {global_mcp_instance}")

            app.mount("/mcp-server", mcp_http_app, name="mcp_http_endpoint")
            app.mount("/mcp-sse", mcp_sse_app, name="mcp_sse_endpoint")

            logger.info(f"FastMCP HTTP app mounted at /mcp-server/mcp (full path: /api/v1/mcp-server/mcp)")
            logger.info(f"FastMCP SSE app mounted at /mcp-sse/sse (full path: /api/v1/mcp-sse/sse)")

            # Final check on the mounted app
            logger.info(f"MCP HTTP app: {mcp_http_app}")
            logger.info(f"MCP SSE app: {mcp_sse_app}")

            logger.info("Startup complete!")

            # Yield control back to the application
            yield

        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            raise
        finally:
            # Shutdown logic
            logger.info("Starting shutdown process...")
            try:
                logger.info("Canceling background tasks...")
                background_tasks = getattr(app.state, 'background_tasks', [])
                for task in background_tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                # Stop batch processors
                logger.info("Stopping batch processors...")
                if hasattr(app.state, 'redis_manager') and app.state.redis_manager:
                    for priority, processor in app.state.redis_manager.batch_processor.processors.items():
                        logger.info(f"Stopping {priority} priority batch processor...")
                        await processor.stop()

                    # Sync data to database
                    logger.info("Syncing data to database...")
                    async for db in get_db():
                        await app.state.redis_manager.sync_redis_to_db(db)
                        break

                    # Stop services
                    logger.info("Stopping services...")
                    await app.state.redis_manager.stop()

                await close_redis_connection()
                await close_db_connection()

                logger.info("Shutdown complete")

            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
                raise

app = FastAPI(
    title="the Barcode API",
    description="""
    The Barcode API allows you to generate various types of barcodes programmatically.
    Rate limits apply based on authentication status and tier level.
    """,
    version=settings.API_VERSION,
    docs_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/",
    openapi_url="/openapi.json",
    lifespan=integrated_lifespan,
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

# Initialize CORS origins before adding middleware
app.state.cors_origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://thebarcodeapi.com",
    "https://api.thebarcodeapi.com"
]

# Add CORS middleware
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


if settings.ENVIRONMENT == "development":
    settings.ALLOWED_HOSTS.extend([
        "localhost",
        "127.0.0.1"
    ])


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

# Include routers
app.include_router(health.router)
app.include_router(barcode.router)
app.include_router(usage.router)
app.include_router(token.router)
app.include_router(admin.router)
app.include_router(bulk_api_router.router)

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
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    redis_stats = await app.state.redis_manager.get_connection_stats()
    logger.debug(f"Redis Stats - Total Connections: {redis_stats.total_connections}, In Use: {redis_stats.in_use_connections}")
    return response

async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)

    # Add rate limit headers if they exist
    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value

    return response

# Add a custom middleware to ensure CORS headers are always present
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")

    if origin in app.state.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"

    return response

# The MCP instance is already stored in app state via integrated_lifespan
# All startup/shutdown logic is handled by the integrated_lifespan function
