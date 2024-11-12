# app/dependencies.py
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from redis.exceptions import RedisError
from typing import Optional

from app.config import settings
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
from app.schemas import UserData

import logging

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_client_ip(request: Request):
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    client_ip = (x_forwarded_for.split(',')[0].strip() if x_forwarded_for else None) or \
                request.headers.get("X-Real-IP") or \
                (request.client.host if request else None)
    return client_ip

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    request: Request = None,
    redis_manager: RedisManager = Depends(get_redis_manager)
) -> UserData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Unauthenticated user
    if token is None:
        try:
            client_ip = await get_client_ip(request)
            logger.debug(f"Client IP: {client_ip}")

            # Try to get existing user data by IP first
            user_data = await redis_manager.get_user_data_by_ip(client_ip)
            if user_data:
                logger.debug(f"Found existing user data for IP {client_ip}")
                return user_data

            # If no existing data found, create new user data
            logger.debug("Creating default user data")
            user_data = await redis_manager.create_default_user_data(client_ip)

            # Store user data (this will also set up IP mapping)
            await redis_manager.set_user_data(user_data)
            return user_data

        except RedisError as e:
            logger.error(f"Redis error: {e}")
            raise HTTPException(status_code=503, detail="Service Unavailable")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # Authenticated user logic remains the same...
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        user_data = await redis_manager.get_user_data_by_username(username)
        if not user_data:
            raise credentials_exception

        is_token_active = await redis_manager.is_token_active(user_data.id, token)
        if not is_token_active:
            raise credentials_exception

        return user_data

    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
