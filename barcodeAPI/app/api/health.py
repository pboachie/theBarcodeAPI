# app/api/health.py

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.schemas import HealthResponse, DetailedHealthResponse
from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.dependencies import get_redis_manager
from app.redis_manager import RedisManager
from app.rate_limiter import rate_limit
from app.security import verify_master_key
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["System Health"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Internal server error occurred"}
                }
            }
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {"detail": "Rate limit exceeded. Try again in 30 seconds."}
                }
            }
        }
    }
)

# Cache configuration
CACHE_DURATION = timedelta(seconds=10)
last_check_time = datetime.min
cached_health_response: Optional[HealthResponse] = None

async def check_database(db: AsyncSession) -> str:
    """
    Check the database connection.

    Args:
        db: AsyncSession database connection

    Returns:
        str: "ok" if database is healthy, "error" otherwise
    """
    try:
        await db.execute(text("SELECT 1"))
        logger.debug("Database health check successful")
        return "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        return "error"

async def get_system_metrics() -> Dict[str, Any]:
    """
    Collect system metrics using psutil.

    Returns:
        Dict containing CPU, memory, and disk metrics
    """
    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_usage": psutil.virtual_memory().percent,
        "memory_total": psutil.virtual_memory().total // (1024 ** 3),  # GB
        "disk_usage": psutil.disk_usage('/').percent
    }

async def detailed_health_check(redis_manager: RedisManager) -> None:
    """
    Perform a detailed health check and store results in Redis.

    Args:
        redis_manager: Redis connection manager
    """
    async with AsyncSessionLocal() as db:
        try:
            # Collect all metrics concurrently
            system_metrics = await get_system_metrics()
            db_status = await check_database(db)
            redis_status = await redis_manager.check_redis()
            redis_details = await redis_manager.get_connection_stats()

            detailed_health = {
                "status": "ok" if all([db_status == "ok", redis_status == "ok"]) else "error",
                "timestamp": datetime.now().isoformat(),
                **system_metrics,
                "database_status": db_status,
                "redis_status": redis_status,
                "redis_details": {
                    "connected_clients": redis_details.connected_clients,
                    "blocked_clients": redis_details.blocked_clients,
                    "tracking_clients": redis_details.tracking_clients
                }
            }

            if detailed_health["status"] != "ok":
                detailed_health["message"] = "One or more system components are not functioning properly"

            # Store in Redis with 5-minute expiration
            await redis_manager.redis.set(
                "detailed_health_check",
                json.dumps(detailed_health),
                ex=300
            )
            logger.debug("Detailed health check completed and stored in Redis")

        except Exception as e:
            logger.error("Error during detailed health check", exc_info=e)
            error_health = {
                "status": "error",
                "message": f"Error occurred during detailed health check: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            await redis_manager.redis.set(
                "detailed_health_check",
                json.dumps(error_health),
                ex=300
            )

@router.get(
    "",
    response_model=HealthResponse,
    summary="Check Server Status",
    include_in_schema=False,
    description="""
    Perform a basic health check on the system.

    Checks the status of critical system components:
    - Database connection
    - Redis connection

    Returns overall system status, API version, and component status.
    Rate limited to 3 requests per 30 seconds.
    """
)
@rate_limit(times=3, interval=30, period="second")
async def health_check(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_manager: RedisManager = Depends(get_redis_manager),
) -> HealthResponse:
    global last_check_time, cached_health_response

    # Return cached response if valid
    if (datetime.now() - last_check_time < CACHE_DURATION and
        cached_health_response is not None):
        return cached_health_response

    try:
        # Check critical components
        db_status = await check_database(db)
        redis_status = await redis_manager.check_redis()

        overall_status = "ok" if all([db_status == "ok", redis_status == "ok"]) else "error"

        # Update cache
        cached_health_response = HealthResponse(
            status=overall_status,
            version=settings.API_VERSION,
            database_status=db_status,
            redis_status=redis_status
        )
        last_check_time = datetime.now()

        # Schedule detailed check
        background_tasks.add_task(detailed_health_check, redis_manager)

        return cached_health_response

    except Exception as e:
        logger.error("Health check failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed due to internal error"
        )

@router.get(
    "/detailed",
    response_model=DetailedHealthResponse,
    include_in_schema=False,
    summary="Detailed System Health Check",
    description="""
    Retrieve comprehensive system health information including:
    - CPU usage
    - Memory utilization
    - Disk space
    - Database status
    - Redis metrics

    Requires master key authentication.
    Rate limited to 3 requests per 30 seconds.
    """,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid master key",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid master key"}
                }
            }
        }
    }
)
@rate_limit(times=3, interval=30, period="second")
async def get_detailed_health(
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(verify_master_key)
) -> DetailedHealthResponse:
    try:
        detailed_health = await redis_manager.redis.get("detailed_health_check")
        if detailed_health:
            return DetailedHealthResponse(**json.loads(detailed_health))

        return DetailedHealthResponse(
            status="unavailable",
            message="Detailed health check data not available. Please try again later."
        )

    except json.JSONDecodeError as e:
        logger.error("Failed to parse detailed health check data", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid health check data format"
        )

    except Exception as e:
        logger.error("Failed to retrieve detailed health check", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving health check data: {str(e)}"
        )