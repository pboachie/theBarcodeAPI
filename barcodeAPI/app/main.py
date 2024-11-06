# app/main.py

import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from pydantic import ValidationError

import logging
import asyncio

from app.api import barcode, usage, health, token, admin
from app.config import settings
from app.barcode_generator import BarcodeGenerationError
from app.database import close_db_connection, init_db, get_db, engine
from app.redis import redis_manager, close_redis_connection, initialize_redis_manager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CustomServerHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["server"] = f"BarcodeAPI/{settings.API_VERSION}"
        return response

app = FastAPI(title="Barcode Generator API", version=settings.API_VERSION)

# Add the custom server header middleware
app.add_middleware(CustomServerHeaderMiddleware)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def log_pool_status():
    while True:
        try:
            pool = redis_manager.redis.connection_pool
            logger.info(f"Redis Pool Status - Max Connections: {pool.max_connections}, In Use: {len(pool._in_use_connections)}, Available: {len(pool._available_connections)}")
        except Exception as e:
            logger.error(f"Error logging pool status: {e}")
        await asyncio.sleep(60)  # Log every minute

@app.on_event("startup")
async def startup():
    logger.info("Starting up...")
    try:
        await init_db()
        await FastAPILimiter.init(redis_manager.redis)
        await initialize_redis_manager()
        asyncio.create_task(log_pool_status())

        # Start the redis_manager in the background
        logger.info("Starting Redis manager in the background...")
        asyncio.create_task(redis_manager.start())

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
    logger.info("Shutdown complete")

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
