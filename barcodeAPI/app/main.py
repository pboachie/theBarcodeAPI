# app/main.py

import asyncio
import gc
import signal
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from pydantic import ValidationError
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

import logging
import asyncio

from app.api import barcode, usage, health, token, admin
from app.config import settings
from app.barcode_generator import BarcodeGenerationError
from app.database import close_db_connection, init_db, get_db
from app.redis import redis_manager, close_redis_connection, initialize_redis_manager
from app.schemas import SecurityScheme

log_directory = settings.LOG_DIRECTORY
os.makedirs(log_directory, exist_ok=True)

# log_level = logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG
log_level = logging.DEBUG
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_directory, "app.log"), mode="a"),
        logging.StreamHandler()
    ]
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

    # Create shutdown event
    shutdown_event = asyncio.Event()

    def signal_handler():
        """Handle shutdown signals"""
        logger.info("Received shutdown signal...")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Startup
        logger.info(f"Initializing in process {current_process}")
        try:
            # if settings.ENVIRONMENT == "development":
            #     gc.set_debug(gc.DEBUG_LEAK)

            await initialize_redis_manager()
            app.state.redis_manager = redis_manager

            # Store batch processor reference in app state
            app.state.batch_processor = redis_manager.batch_processor
            # Verify Redis manager state
            logger.info("Verifying Redis manager state...")
            if not redis_manager.batch_processor:
                raise RuntimeError("Batch processor not initialized")

            for priority, processor in redis_manager.batch_processor.processors.items():
                if not processor.running:
                    logger.error(f"{priority} processor not running")
                    raise RuntimeError(f"{priority} processor failed to start")
                logger.info(f"{priority} processor running")

            # Initialize other services
            logger.info("Initializing database...")
            await init_db()

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

            logger.info("Startup complete!")
            yield

            # Wait for shutdown signal
            await shutdown_event.wait()

        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            raise

        finally:
            # Shutdown
            logger.info("Starting shutdown process...")
            try:
                # Remove signal handlers
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.remove_signal_handler(sig)

                # Cancel background tasks
                logger.info("Canceling background tasks...")
                for task in app.state.background_tasks:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                # Stop batch processors
                logger.info("Stopping batch processors...")
                for priority, processor in redis_manager.batch_processor.processors.items():
                    logger.info(f"Stopping {priority.name} priority batch processor...")
                    await processor.stop()

                # Sync data to database
                logger.info("Syncing data to database...")
                async for db in get_db():
                    await redis_manager.sync_redis_to_db(db)
                    break

                # Stop services
                logger.info("Stopping services...")
                await redis_manager.stop()
                await close_redis_connection()
                await close_db_connection()

            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
                raise
            finally:
                # Final cleanup
                gc.collect()
                logger.info("Shutdown complete")

    finally:
        # Remove signal handlers
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
    title="the Barcode API",
    description="""
    The Barcode API allows you to generate various types of barcodes programmatically.
    Rate limits apply based on authentication status and tier level.
    """,
    version=settings.API_VERSION,
    docs_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
    servers=[{"url": settings.SERVER_URL}],
    contact={
        "name": "Barcode API Support",
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
            logger.info(f"Redis Pool Status - Max Connections: {pool.max_connections}, In Use: {len(pool._in_use_connections)}, Available: {len(pool._available_connections)}")
        except Exception as e:
            logger.error(f"Error logging pool status: {e}")
        await asyncio.sleep(60)

# Remove or comment out the startup and shutdown event handlers to prevent duplicate initialization
# @app.on_event("startup")
# async def startup():
#     logger.info("Starting up...")
#     try:
#         if settings.ENVIRONMENT == "development":
#             gc.set_debug(gc.DEBUG_LEAK)
#         await initialize_redis_manager()
#         await init_db()
#         await FastAPILimiter.init(redis_manager.redis)
#         await redis_manager.start()
#         # ...other startup tasks...
#     except Exception as e:
#         logger.error(f"Error during startup: {e}", exc_info=True)
#         raise

# @app.on_event("shutdown")
# async def shutdown_event():
#     logger.info("Starting shutdown process...")
#     try:
#         for priority, processor in redis_manager.batch_processor.processors.items():
#             logger.info(f"Stopping {priority.name} priority batch processor...")
#             await processor.stop()
#         await redis_manager.sync_redis_to_db(db)
#         await redis_manager.stop()
#         await close_redis_connection()
#         await close_db_connection()
#         gc.collect()
#         logger.info("Shutdown complete")
#     except Exception as e:
#         logger.error(f"Error during shutdown: {e}", exc_info=True)
#         raise

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
    error_messages = [f"{'.'.join(err['loc'])}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=400,
        content={"message": error_messages[0], "error_type": "ValidationError"}
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(exc: ValidationError):
    logger.error(f"Pydantic validation error: {exc}")
    error_messages = [f"{'.'.join(err['loc'])}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=400,
        content={"message": error_messages[0], "error_type": "ValidationError"}
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
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

