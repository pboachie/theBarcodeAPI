# app/rate_limiter.py

from functools import wraps
from typing import Callable
import logging
from fastapi import Request, HTTPException, Depends
from starlette.status import HTTP_429_TOO_MANY_REQUESTS, HTTP_500_INTERNAL_SERVER_ERROR
from app.redis_manager import RedisManager
from app.dependencies import get_client_ip
from app.redis import get_redis_manager
from app.lua_scripts import RATE_LIMIT_SCRIPT

logger = logging.getLogger(__name__)

def rate_limit(times: int, interval: float, period: str):
    """Rate limiting decorator"""
    logger.debug(f"Rate limiter set to {times} requests per {interval} {period}")
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            redis_manager: RedisManager = kwargs.get('redis_manager')

            if not request or not redis_manager:
                raise HTTPException(
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error. Missing required dependencies."
                )

            client_ip = await get_client_ip(request)
            key = f"rate_limit:{client_ip}:{period}"

            try:
                current = await redis_manager.redis.eval(
                    RATE_LIMIT_SCRIPT,
                    1, key, interval, times
                )
                if current == -1:
                    raise HTTPException(
                        status_code=HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded. Please try again later."
                    )
            except Exception as ex:
                logger.error(f"Rate limit check failed: {ex}")
                raise HTTPException(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit check failed. Please try again later."
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

