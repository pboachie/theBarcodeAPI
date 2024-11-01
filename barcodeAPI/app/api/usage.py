# app/api/usage.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from app.dependencies import get_current_user, get_client_ip
from app.schemas import UsageResponse, UserData
from app.config import settings
from app.rate_limiter import rate_limit
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
from datetime import datetime, timedelta
import pytz
import logging

router = APIRouter(prefix="/usage", tags=["Usage"])

logger = logging.getLogger(__name__)

@router.get("", response_model=UsageResponse, summary="Get user usage statistics")
async def get_usage(
    request: Request,
    current_user: UserData = Depends(get_current_user),
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: bool = Depends(rate_limit(times=30, interval=1, period="minutes"))
):
    """
    Retrieve usage statistics for the current user or IP address.

    This endpoint returns the number of requests made today, the request limit,
    and the remaining requests for the current period.

    - For authenticated users, the limit is based on their account tier.
    - For unauthenticated users, a default limit is applied based on their IP address.

    Rate limited to 30 requests per minute.
    """
    client_ip = await get_client_ip(request)
    user_data = await redis_manager.get_user_data(user_id=current_user.id, ip_address=client_ip)

    if not user_data:
        user_data = UserData(
            id=current_user.id,
            username=current_user.username,
            tier=current_user.tier,
            ip_address=client_ip,
            remaining_requests=settings.RateLimit.get_limit(current_user.tier),
            requests_today=0,
            last_reset=datetime.now(pytz.utc)
        )
        await redis_manager.set_user_data(user_data)

    # Check and reset usage if necessary
    pst_tz = pytz.timezone("America/Los_Angeles")
    current_time_pst = datetime.now(pytz.utc).astimezone(pst_tz)
    start_of_day_pst = current_time_pst.replace(hour=0, minute=0, second=0, microsecond=0)

    last_reset = user_data.last_reset.astimezone(pst_tz)
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

    add_headers = {
        "X-Rate-Limit-Requests": str(requests_limit),
        "X-Rate-Limit-Remaining": str(user_data.remaining_requests),
        "X-Rate-Limit-Reset": str(int((user_data.last_reset + timedelta(days=1) - datetime.now(pytz.utc)).total_seconds())),
        "Server": "TheBarcodeAPI/"  + settings.API_VERSION
    }

    usage_response = UsageResponse(
        requests_today=user_data.requests_today,
        requests_limit=requests_limit,
        remaining_requests=user_data.remaining_requests
    )

    response = JSONResponse(content=usage_response.dict())
    response.headers.update(add_headers)

    return response

# Endpoint to monitor batch processing metrics
@router.get("/usage/metrics")
async def get_metrics(
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    return await redis_manager.get_metrics()


