from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from app.dependencies import get_current_user, get_client_ip
from app.schemas import BatchPriority, UsageResponse, UserData
from app.config import settings
from app.rate_limiter import rate_limit
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
from app.security import verify_master_key
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
import logging
from functools import lru_cache

router = APIRouter(prefix="/usage", tags=["Usage"])
logger = logging.getLogger(__name__)

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

@router.get("/metrics", summary="Get batch processing metrics", include_in_schema=False)
async def get_metrics(
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(verify_master_key),
    __: None = Depends(rate_limit(times=RATE_LIMIT, interval=1, period="second"))
):
    """Get metrics for batch processing operations and Redis status"""
    try:
        return JSONResponse(
            content=await redis_manager.get_metrics(),
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error retrieving metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving metrics"
        )

@router.get("/", response_model=UsageResponse)
async def get_usage(
    request: Request,
    redis_manager: RedisManager = Depends(get_redis_manager),
    user_data: UserData = Depends(get_current_user),
    _: None = Depends(rate_limit(times=RATE_LIMIT, interval=1, period="second"))
):
    """
    Retrieve usage statistics for the current user or IP address.

    This endpoint returns the number of requests made today, the request limit,
    and the remaining requests for the current period.

    - For authenticated users, the limit is based on their account tier.
    - For unauthenticated users, a default limit is applied based on their IP address.

    Rate limited to 5 requests per second.
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

        logger.debug( # Log usage stats
            "Usage stats",
            extra={
                "requests_today": user_data.requests_today,
                "remaining_requests": user_data.remaining_requests,
                "user_tier": user_data.tier
            }
        )

        return JSONResponse(
            content=create_usage_response(user_data, user_limits),
            headers=create_usage_headers(user_limits, user_data.remaining_requests, user_data.last_reset)
        )

    except Exception as ex:
        logger.error("Usage retrieval error", exc_info=ex)
        raise HTTPException(
            status_code=500,
            detail="Error retrieving usage statistics"
        )
