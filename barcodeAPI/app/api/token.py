# app/api/token.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models import User
from app.security import create_access_token, verify_password
from app.rate_limiter import rate_limit
from app.schemas import Token
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/token", tags=["Authentication"])

@router.post("", response_model=Token, summary="Create user access token", include_in_schema=False)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis_manager: RedisManager = Depends(get_redis_manager),
    _: None = Depends(rate_limit(times=5, interval=5, period="minutes"))
):
    """
    Create an access token for user authentication.

    - **username**: The user's username
    - **password**: The user's password

    Rate limited to 5 requests per 5 minutes per IP address.
    """
    try:
        async with db.begin():
            result = await db.execute(select(User).filter(User.username == form_data.username))
            user = result.scalar_one_or_none()

        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = await create_access_token(data={"sub": user.username}, db=db, redis_manager=redis_manager)
        return Token(access_token=access_token, token_type="bearer")
    finally:
        await db.close()

# Rate limit all other endpoints to 1 request per 15 minutes
@router.get("", status_code=status.HTTP_405_METHOD_NOT_ALLOWED, summary="Method not allowed", include_in_schema=False)
@router.put("", status_code=status.HTTP_405_METHOD_NOT_ALLOWED, summary="Method not allowed", include_in_schema=False)
@router.delete("", status_code=status.HTTP_405_METHOD_NOT_ALLOWED, summary="Method not allowed", include_in_schema=False)
async def invalid_token_methods(
    _: None = Depends(rate_limit(times=1, interval=15, period="minutes"))
):
    """
    These methods are not allowed for the token endpoint.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Only POST method is allowed for token creation",
    )