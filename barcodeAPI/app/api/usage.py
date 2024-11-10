# app/api/usage.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
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
import logging

router = APIRouter(prefix="/usage", tags=["Usage"])

logger = logging.getLogger(__name__)

@router.get("/metrics",
    summary="Get batch processing metrics",
    include_in_schema=False
)
async def get_metrics(
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(verify_master_key)
):
    """
    Get metrics for batch processing operations and Redis status
    """
    try:
        metrics = await redis_manager.get_metrics()
        return JSONResponse(
            content=metrics,
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving metrics"
        )

@router.get("/", response_model=UsageResponse)
@rate_limit(times=10000 if settings.ENVIRONMENT == 'development' else 5, interval=1, period="second")
async def get_usage(
    request: Request,
    redis_manager: RedisManager = Depends(get_redis_manager),
    user_data: UserData = Depends(get_current_user)
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
        # Check and reset usage if necessary
        pst_tz = pytz.timezone("America/Los_Angeles")
        current_time_pst = datetime.now(pytz.utc).astimezone(pst_tz)
        start_of_day_pst = current_time_pst.replace(hour=0, minute=0, second=0, microsecond=0)

        last_reset = user_data.last_reset.astimezone(pst_tz) if user_data.last_reset else current_time_pst
        user_limits = settings.RateLimit.get_limit(user_data.tier)

        if last_reset < start_of_day_pst:
            logger.info("Resetting daily usage count")
            user_data.requests_today = 0
            user_data.last_reset = current_time_pst
            user_data.remaining_requests = user_limits
            await redis_manager.set_user_data(user_data)

        requests_limit = user_limits

        if user_data.last_reset.tzinfo is None:
            user_data.last_reset = user_data.last_reset.replace(tzinfo=pytz.utc)

        logger.info(f"Current usage - Requests today: {user_data.requests_today}, Remaining: {user_data.remaining_requests}")

        # Return response with headers
        add_headers = {
            "X-Rate-Limit-Requests": str(requests_limit),
            "X-Rate-Limit-Remaining": str(user_data.remaining_requests),
            "X-Rate-Limit-Reset": str(int((user_data.last_reset + timedelta(days=1) - datetime.now(pytz.utc)).total_seconds())),
            "Server": "TheBarcodeAPI/" + settings.API_VERSION
        }

        response = JSONResponse(
            content=UsageResponse(
                requests_today=user_data.requests_today,
                requests_limit=requests_limit,
                remaining_requests=user_data.remaining_requests
            ).dict()
        )
        response.headers.update(add_headers)
        return response

    except Exception as ex:
        logger.error(f"Error getting usage stats: {ex}")
        raise
