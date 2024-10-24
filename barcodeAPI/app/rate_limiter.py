# app/rate_limiter.py

from fastapi import Request, HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from app.redis_manager import RedisManager
from app.dependencies import get_client_ip
import logging
from typing import Callable
import functools

logger = logging.getLogger(__name__)

def rate_limit(times: int, interval: int, period: str):
    """Rate limiting decorator with batched operations"""
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

            redis_manager = None
            for arg in args:
                if isinstance(arg, RedisManager):
                    redis_manager = arg
                    break
            if not redis_manager:
                redis_manager = kwargs.get('redis_manager')

            if not redis_manager:
                return await func(*args, **kwargs)

            client_ip = await get_client_ip(request)

            # Implement rate limiting logic here
            key = f"rate_limit:{client_ip}:{period}"
            current = await redis_manager.redis.incr(key)
            if current == 1:
                await redis_manager.redis.expire(key, interval)
            if current > times:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                raise HTTPException(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator