# app/security.py

import re
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status, Header
import logging

from app.models import ActiveToken, User
from app.redis_manager import RedisManager
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
logger = logging.getLogger(__name__)

async def create_access_token(data: dict, db: AsyncSession, redis_manager: RedisManager):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    user_result = await db.execute(select(User).filter(User.username == data.get("sub")))
    user = user_result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Store the token in Redis
    await redis_manager.add_active_token(user.id, encoded_jwt, expire_time=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    return encoded_jwt

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def validate_password_strength(password: str) -> bool:
    """
    Validate the strength of a password.

    Rules:
    - At least 8 characters long
    - Contains at least one digit
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one special character
    """
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters long")

    if not re.search(r"\d", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one digit")

    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one lowercase letter")

    if not re.search(r"[ !@#$%&'()*+,-./[\\\]^_`{|}~"+r'"]', password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one special character")

    return True

async def verify_master_key(master_key: str = Header(...)):
    if master_key != settings.MASTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master key",
        )
