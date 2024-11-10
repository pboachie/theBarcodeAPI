# app/rate_limiter.py

from functools import wraps
import logging
from fastapi import Request, HTTPException, Depends
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from app.redis_manager import RedisManager
from app.dependencies import get_client_ip
from app.redis import get_redis_manager
from app.lua_scripts import RATE_LIMIT_SCRIPT

logger = logging.getLogger(__name__)

def rate_limit(times: int, interval: int = 1, period: str = "second"):
    """Rate limiting decorator"""
    async def dependency(
        request: Request,
        redis_manager: RedisManager = Depends(get_redis_manager)
    ):
        client_ip = await get_client_ip(request)
        key = f"rate_limit:{client_ip}:{period}"

        try:
            current = await redis_manager.redis.eval(
                RATE_LIMIT_SCRIPT,
                1,          # numkeys
                key,        # KEYS[1]
                interval,   # ARGV[1]
                times      # ARGV[2]
            )
            if current == -1:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                raise HTTPException(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
        except Exception as ex:
            logger.error(f"Rate limit check failed: {ex}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )

    return dependency

