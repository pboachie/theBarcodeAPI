# app/main.py

import asyncio
import gc
import io
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from pydantic import ValidationError
from fastapi.openapi.utils import get_openapi

import logging
import asyncio

from app.api import barcode, usage, health, token, admin
from app.config import settings
from app.barcode_generator import BarcodeGenerationError
from app.database import close_db_connection, init_db, get_db, engine
from app.redis import redis_manager, close_redis_connection, initialize_redis_manager
from app.schemas import SecurityScheme

if settings.ENVIRONMENT == "production":
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

class CustomServerHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["server"] = f"BarcodeAPI/{settings.API_VERSION}"
        return response

app = FastAPI(
    title="the Barcode API",
    description="""
    The Barcode API allows you to generate various types of barcodes programmatically.
    Rate limits apply based on authentication status and tier level.
    """,
    version=settings.API_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT == "development" else None,
    contact={
        "name": "API Support",
        "url": "https://thebarcodeapi.com/support",
        "email": "support@boachiefamily.net",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }
)

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
        "bearerAuth": SecurityScheme().dict()
    }

    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"bearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Custom middleware to add server header
app.add_middleware(CustomServerHeaderMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",  # Add React development server
        "http://localhost:8000", # Add FastAPI development server
        "https://thebarcodeapi.com"
    ],
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

async def log_pool_status():
    while True:
        try:
            pool = redis_manager.redis.connection_pool
            logger.info(f"Redis Pool Status - Max Connections: {pool.max_connections}, In Use: {len(pool._in_use_connections)}, Available: {len(pool._available_connections)}")
        except Exception as e:
            logger.error(f"Error logging pool status: {e}")
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup():
    logger.info("Starting up...")
    try:
        if settings.ENVIRONMENT == "development":
            gc.set_debug(gc.DEBUG_LEAK)

        # Add CORS origins to app state
        app.state.cors_origins = [
            "http://localhost",
            "http://localhost:3000", # Add React development server
            "http://localhost:8000", # Add FastAPI development server
            "https://thebarcodeapi.com"
        ]

        await initialize_redis_manager()
        await init_db()
        await FastAPILimiter.init(redis_manager.redis)

        # Start the redis_manager in the background
        logger.info("Starting Redis manager in the background...")
        asyncio.create_task(redis_manager.start())

        logger.info("Starting background tasks...")
        asyncio.create_task(log_memory_usage())
        asyncio.create_task(log_pool_status())


        async for db in get_db():
            await redis_manager.sync_all_username_mappings(db)
            # await redis_manager.reset_daily_usage()
            break

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    # Sync data to db before shutting down
    async for db in get_db():
        await redis_manager.sync_to_database(db)
        break

    await redis_manager.stop()
    await close_redis_connection()
    await close_db_connection()
    gc.collect()
    logger.info("Shutdown complete")

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
        content={"message": "An unexpected error occurred. Please try again later.", "error_type": "InternalServerError"}
    )

@app.exception_handler(BarcodeGenerationError)
async def barcode_generation_exception_handler(request: Request, exc: BarcodeGenerationError):
    logger.error(f"Barcode generation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"message": exc.message, "error_type": exc.error_type}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    error_messages = [f"{'.'.join(err['loc'])}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=400,
        content={"message": error_messages[0], "error_type": "ValidationError"}
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
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
