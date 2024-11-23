from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from app.dependencies import get_current_user, get_redis_manager
from app.schemas import UsageResponse, UserData
from app.config import settings
from app.rate_limiter import rate_limit
from app.redis_manager import RedisManager
from app.security import verify_master_key
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
import asyncio.log as logging
from functools import lru_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/usage",
    tags=["Usage Statistics"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Resource not found"}
                }
            }
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Internal server error occurred"}
                }
            }
        }
    }
)

RATE_LIMIT = 100 if settings.ENVIRONMENT == 'development' else 50

PST_TIMEZONE = pytz.timezone('America/Los_Angeles')
UTC_TIMEZONE = pytz.UTC

@lru_cache()
def get_user_limits(tier: str) -> int:
    """Cache user limits based on tier to avoid repeated lookups"""
    return settings.RateLimit.get_limit(tier)

def get_reset_time(last_reset: datetime) -> int:
    """Calculate reset time in seconds"""
    return int((last_reset + timedelta(days=1) - datetime.now(UTC_TIMEZONE)).total_seconds())

def create_usage_headers(user_limits: int, remaining_requests: int, last_reset: datetime) -> Dict[str, str]:
    """Create response headers with rate limit information"""
    return {
        "X-Rate-Limit-Requests": str(user_limits),
        "X-Rate-Limit-Remaining": str(remaining_requests),
        "X-Rate-Limit-Reset": str(get_reset_time(last_reset)),
        "Server": f"TheBarcodeAPI/{settings.API_VERSION}"
    }

def create_usage_response(user_data: UserData, user_limits: int) -> Dict[str, Any]:
    """Create standardized usage response"""
    reset_time = user_data.last_reset + timedelta(days=1)
    return {
        "requests_today": user_data.requests_today,
        "requests_limit": user_limits,
        "remaining_requests": user_data.remaining_requests,
        "reset_time": reset_time.isoformat()
    }

@router.get(
    "/metrics",
    summary="Retrieve Batch Processing Metrics",
    description="""
    Get detailed metrics for batch processing operations and Redis status.

    This endpoint provides:
    - Current batch processing queue status
    - Processing time statistics
    - Redis connection health
    - System resource utilization

    Requires master key authentication.
    """,
    include_in_schema=False,
    response_description="Detailed metrics for batch processing and system status",
    responses={
        200: {
            "description": "Successful metrics retrieval",
            "content": {
                "application/json": {
                    "example": {
                        "queue_size": 42,
                        "processing_rate": 156.7,
                        "average_processing_time": 0.31
                    }
                }
            }
        },
        401: {
            "description": "Invalid or missing master key",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid master key"}
                }
            }
        }
    }
)
@rate_limit(times=RATE_LIMIT, interval=1, period="second")
async def get_metrics(
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(verify_master_key)
):
    """
    Retrieve detailed metrics for batch processing operations.

    Dependencies:
        - Redis manager for accessing metrics data
        - Master key verification for security
        - Rate limiting to prevent abuse

    Returns:
        JSONResponse: Metrics data including queue status and processing statistics

    Raises:
        HTTPException: If metrics retrieval fails or authentication is invalid
    """
    try:
        return JSONResponse(
            content=await redis_manager.get_metrics(),
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Metrics retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving metrics data"
        )

@router.get(
    "/",
    response_model=UsageResponse,
    summary="Get Current Usage Statistics",
    description="""
    Retrieve detailed usage statistics for the current user or IP address.

    Provides:
    - Number of requests made today
    - Request limit based on user tier
    - Remaining requests for current period
    - Time until limit reset

    Authentication:
    - Authenticated users: Limits based on account tier
    - Unauthenticated users: IP-based default limits

    Rate limiting: 50 requests per second in production, 100 in development.
    """,
    response_description="Current usage statistics and limits",
    responses={
        200: {
            "description": "Successful usage statistics retrieval",
            "headers": {
                "X-Rate-Limit-Requests": {
                    "description": "Total requests allowed per day",
                    "schema": {"type": "integer"}
                },
                "X-Rate-Limit-Remaining": {
                    "description": "Remaining requests for current period",
                    "schema": {"type": "integer"}
                },
                "X-Rate-Limit-Reset": {
                    "description": "Seconds until limit reset",
                    "schema": {"type": "integer"}
                }
            },
            "content": {
                "application/json": {
                    "example": {
                        "requests_today": 42,
                        "requests_limit": 1000,
                        "remaining_requests": 958,
                        "reset_time": "2024-11-10T00:00:00Z"
                    }
                }
            }
        }
    }
)
@rate_limit(times=RATE_LIMIT, interval=1, period="second")
async def get_usage(
    request: Request,
    redis_manager: RedisManager = Depends(get_redis_manager),
    user_data: UserData = Depends(get_current_user)):
    """
    Get detailed usage statistics for the current user.

    The endpoint manages usage tracking and limit enforcement:
    - Tracks requests per day
    - Enforces tier-based limits
    - Handles automatic reset at midnight PST
    - Provides detailed usage headers

    Args:
        request: FastAPI request object
        redis_manager: Redis connection manager
        user_data: Current user data from authentication

    Returns:
        JSONResponse: Usage statistics with rate limit headers

    Raises:
        HTTPException: For rate limit exceeded or server errors
    """
    try:
        current_time_pst = datetime.now(PST_TIMEZONE)
        start_of_day_pst = current_time_pst.replace(hour=0, minute=0, second=0, microsecond=0)
        last_reset = user_data.last_reset.astimezone(PST_TIMEZONE)

        user_limits = get_user_limits(user_data.tier)

        # Reset usage if new day has started
        if last_reset < start_of_day_pst:
            user_data.requests_today = 0
            user_data.remaining_requests = user_limits
            user_data.last_reset = current_time_pst
            await redis_manager.set_user_data(user_data)

        logger.debug(
            "Usage stats",
            extra={
                "requests_today": user_data.requests_today,
                "remaining_requests": user_data.remaining_requests,
                "user_tier": user_data.tier,
                "last_reset": user_data.last_reset.isoformat()
            }
        )

        return JSONResponse(
            content=create_usage_response(user_data, user_limits),
            headers=create_usage_headers(user_limits, user_data.remaining_requests, user_data.last_reset)
        )

    except Exception as ex:
        logger.error("Usage statistics error", exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving usage statistics"
        )
