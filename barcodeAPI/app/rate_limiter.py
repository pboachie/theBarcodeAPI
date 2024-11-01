# app/rate_limiter.py

import functools
import logging
from typing import Callable
from fastapi import Request, HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from app.redis_manager import RedisManager
from app.dependencies import get_client_ip

logger = logging.getLogger(__name__)

RATE_LIMIT_SCRIPT = """
local current
current = redis.call("INCR", KEYS[1])
if tonumber(current) == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
if tonumber(current) > tonumber(ARGV[2]) then
    return -1
end
return current
"""

def rate_limit(times: int, interval: int, period: str):
    """Rate limiting decorator with Lua script for atomic operations"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                return await func(*args, **kwargs)

            redis_manager: RedisManager = kwargs.get('redis_manager')
            if not redis_manager:
                for arg in args:
                    if isinstance(arg, RedisManager):
                        redis_manager = arg
                        break
            if not redis_manager:
                return await func(*args, **kwargs)

            client_ip = await get_client_ip(request)
            key = f"rate_limit:{client_ip}:{period}"

            try:
                current = await redis_manager.redis.eval(
                    RATE_LIMIT_SCRIPT,
                    1,          # numkeys
                    key,        # KEYS[1]
                    interval,   # ARGV[1]
                    times       # ARGV[2]
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

            return await func(*args, **kwargs)
        return wrapper
    return decorator