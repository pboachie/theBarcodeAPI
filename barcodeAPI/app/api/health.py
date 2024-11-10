# app/api/health.py

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.schemas import HealthResponse, DetailedHealthResponse
from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
from app.rate_limiter import rate_limit
from app.security import verify_master_key
import logging
import psutil
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["System Health"])

last_check_time = datetime.min
cached_health_response = None

@router.get("", response_model=HealthResponse, summary="Check Server Status")
async def health_check(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(rate_limit(times=3, interval=30, period="second"))
):
    """
    Perform a basic health check on the system.

    This endpoint checks the status of critical system components:
    - Database connection
    - Redis connection

    It returns:
    - Overall system status
    - API version
    - Individual status of database and Redis

    The overall status is "ok" if all components are functioning properly,
    and "error" if any component is not working as expected.

    Rate limited to 3 requests per 30 seconds.
    """
    global last_check_time, cached_health_response

    # Use cached response if it's less than 10 seconds old
    if datetime.now() - last_check_time < timedelta(seconds=10) and cached_health_response:
        return cached_health_response

    try:
        db_status = await check_database(db)
        redis_status = await redis_manager.check_redis()

        overall_status = "ok" if db_status == "ok" and redis_status == "ok" else "error"

        cached_health_response = HealthResponse(
            status=overall_status,
            version=settings.API_VERSION,
            database_status=db_status,
            redis_status=redis_status
        )
        last_check_time = datetime.now()

        # Trigger detailed health check in the background
        background_tasks.add_task(detailed_health_check, redis_manager)

        return cached_health_response
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return HealthResponse(
            status="error",
            version=settings.API_VERSION,
            database_status="error",
            redis_status="error"
        )

@router.get("/detailed", response_model=DetailedHealthResponse, summary="Detailed system health check", include_in_schema=False)
async def get_detailed_health(
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(verify_master_key),
    __: None = Depends(rate_limit(times=3, interval=30, period="second"))
):
    """
    Retrieve the results of the latest detailed health check.

    This endpoint returns more comprehensive health information about the system,
    including CPU usage, memory usage, and disk space.

    Rate limited to 3 requests per 30 seconds.
    """
    try:
        detailed_health = await redis_manager.redis.get("detailed_health_check")
        if detailed_health:
            return DetailedHealthResponse(**eval(detailed_health))
        else:
            return DetailedHealthResponse(
                status="unavailable",
                message="Detailed health check data not available. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in detailed health check: {str(e)}")
        return DetailedHealthResponse(
            status="error",
            message=f"Error retrieving health check data: {str(e)}"
        )

async def check_database(db: AsyncSession) -> str:
    """Check the database connection."""
    try:
        await db.execute(text("SELECT 1"))
        logger.debug("Database health check successful")
        return "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return "error"

async def detailed_health_check(redis_manager: RedisManager):
    """Perform a detailed health check and store results in Redis."""
    async with AsyncSessionLocal() as db:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            memory_total = psutil.virtual_memory().total // (1024 ** 3)  # Convert to GB
            disk_usage = psutil.disk_usage('/').percent

            db_status = await check_database(db)
            redis_status = await redis_manager.check_redis()
            redis_details = await redis_manager.get_connection_stats()

            detailed_health = {
                "status": "ok" if db_status == "ok" and redis_status == "ok" else "error",
                "timestamp": datetime.now().isoformat(),
                "cpu_usage": cpu_usage,
                "memory_usage": f"{memory_usage}",
                "memory_total": memory_total,
                "disk_usage": disk_usage,
                "database_status": db_status,
                "redis_status": redis_status,
                "redis_details": {
                    "connected_clients": redis_details.connected_clients,
                    "blocked_clients": redis_details.blocked_clients,
                    "tracking_clients": redis_details.tracking_clients
                }
            }

            if db_status != "ok" or redis_status != "ok":
                detailed_health["message"] = "One or more system components are not functioning properly"

            await redis_manager.redis.set("detailed_health_check", str(detailed_health), ex=300)  # Expire after 5 minutes
            logger.debug("Detailed health check completed and stored in Redis")
        except Exception as e:
            logger.error(f"Error during detailed health check: {e}")
            error_health = {
                "status": "error",
                "message": f"Error occurred during detailed health check: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            await redis_manager.redis.set("detailed_health_check", str(error_health), ex=300)