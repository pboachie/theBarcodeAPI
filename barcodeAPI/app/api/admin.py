# app/api/admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app import models
from app.dependencies import get_current_user
from app.security import get_password_hash, validate_password_strength, verify_master_key
from app.config import settings
from app.schemas import UserCreate, UsersResponse, UserCreatedResponse, UserData
from app.rate_limiter import rate_limit
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/admin/users", response_model=UsersResponse)
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    _: None = Depends(verify_master_key),
    __: bool = Depends(rate_limit(times=75, interval=15, period="minutes")),
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    Endpoint to retrieve a list of users.

    This endpoint fetches user data from the database and enriches it with additional
    information from Redis. If the user data is not available in Redis, a default
    UserData object is created.

    Args:
        db (AsyncSession): The database session dependency.
        current_user (models.User): The currently authenticated user.
        _ (None): Dependency to verify the master key.
        __ (bool): Dependency to enforce rate limiting.
        redis_manager (RedisManager): The Redis manager dependency.

    Returns:
        UsersResponse: A response model containing the list of users.
    """
    users = []
    try:
        async with db.begin():
            result = await db.execute(select(models.User))
            db_users = result.scalars().all()

        for user in db_users:
            user_data = await redis_manager.get_user_data(user_id=user.id, ip_address=current_user.ip_address)
            if user_data:
                users.append(user_data.dict())
            else:
                # If user data is not in Redis, create a default UserData object
                users.append(UserData(
                    id=user.id,
                    username=user.username,
                    tier=user.tier,
                    ip_address=None,
                    remaining_requests=settings.RateLimit.get_limit(user.tier),
                    requests_today=0,
                    last_reset=datetime.now()
                ).dict())

        return UsersResponse(users=users)
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    finally:
        await db.close()

@router.post("/admin/users", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    _: None = Depends(verify_master_key),
    __: bool = Depends(rate_limit(times=10, interval=15, period="minutes")),
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    Create a new user.

    This endpoint allows an admin to create a new user. It performs several checks and operations:
    1. Verifies the master key.
    2. Applies rate limiting to prevent abuse.
    3. Checks if the username is already registered.
    4. Validates the strength of the provided password.
    5. Hashes the password and stores the new user in the database.
    6. Initializes user data in Redis for rate limiting and other purposes.

    Args:
        user (UserCreate): The user data for creating a new user.
        db (AsyncSession): The database session dependency.
        current_user (models.User): The current authenticated user.
        _ (None): Dependency to verify the master key.
        __ (bool): Dependency to apply rate limiting.
        redis_manager (RedisManager): The Redis manager dependency.

    Returns:
        UserCreatedResponse: A response object containing a success message, the new user's ID, tier, and username.

    Raises:
        HTTPException: If the username is already registered or if there is an error during user creation.
    """
    try:
        async with db.begin():
            # Check if user already exists
            result = await db.execute(select(models.User).filter(models.User.username == user.username))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )

            validate_password_strength(user.password)
            hashed_password = get_password_hash(user.password)
            new_user = models.User(username=user.username, hashed_password=hashed_password, tier=user.tier.value)
            db.add(new_user)
            await db.flush()
            await db.refresh(new_user) # Refresh the user object to get the ID

        # Initialize user data in Redis
        user_data = UserData(
            id=new_user.id,
            username=new_user.username,
            ip_address=None,
            tier=new_user.tier,
            remaining_requests=settings.RateLimit.get_limit(new_user.tier),
            requests_today=0,
            last_reset=datetime.now()
        )
        await redis_manager.set_user_data(user_data)
        await redis_manager.set_username_to_id_mapping(new_user.username, new_user.id)

        return UserCreatedResponse(message="User created successfully", user_id=new_user.id, tier=new_user.tier, username=new_user.username)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.post("/admin/sync-db")
async def sync_database(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    _: None = Depends(verify_master_key),
    __: bool = Depends(rate_limit(times=10, interval=5, period="minutes")),
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    Endpoint to synchronize the database with the Redis cache.
    This endpoint is protected and requires the following dependencies:
    - `db`: An asynchronous database session.
    - `current_user`: The current authenticated user.
    - `verify_master_key`: A dependency to verify the master key.
    - `rate_limit`: A rate limiter to restrict the number of requests.
    - `redis_manager`: A manager to handle Redis operations.
    Returns:
        JSONResponse: A response indicating the success or failure of the database synchronization.
    Raises:
        HTTPException: If there is an error during the synchronization process.
    """
    try:
        await redis_manager.sync_to_database(db)
        return JSONResponse(content={"message": "Database sync completed successfully"}, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error syncing database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error syncing database"
        )