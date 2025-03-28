# app/api/admin.py

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app import models
from app.dependencies import get_current_user
from app.security import get_password_hash, validate_password_strength, verify_master_key
from app.config import settings
from app.schemas import BatchPriority, UserCreate, UsersResponse, UserCreatedResponse, UserData
from app.rate_limiter import rate_limit
from app.redis import get_redis_manager
from app.redis_manager import RedisManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/admin/users", response_model=UsersResponse, include_in_schema=False)
@rate_limit(times=75, interval=15, period="minutes")
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(get_current_user),
    _: None = Depends(verify_master_key),
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    Endpoint to retrieve a list of users.

    Args:
        db: Database session
        current_user: Current authenticated user
        _: Master key verification dependency
        __: Rate limiting dependency
        redis_manager: Redis manager for caching

    Returns:
        UsersResponse: List of user data

    Raises:
        HTTPException: If there's an error retrieving users
    """
    users_data = []
    redis_batch_tasks = []

    try:
        async with db.begin():
            result = await db.execute(select(models.User))
            db_users = result.scalars().all()

        for user in db_users:
            try:
                # Get user data from Redis using batch processor
                user_data = await redis_manager.batch_processor.add_to_batch(
                    "get_user_data",
                    {"user_id": user.id},  # Pass as dict for clearer unpacking
                    priority=BatchPriority.HIGH
                )

                current_time = datetime.now()

                if user_data and isinstance(user_data, UserData):
                    # Use existing Redis data
                    response_item = {
                        "id": str(user_data.id),
                        "username": user_data.username,
                        "tier": user_data.tier,
                        "ip_address": user_data.ip_address,
                        "remaining_requests": user_data.remaining_requests,
                        "requests_today": user_data.requests_today,
                        "last_request": user_data.last_request.isoformat() if user_data.last_request else None,
                        "last_reset": user_data.last_reset.isoformat() if user_data.last_reset else None
                    }
                else:
                    # Create default data
                    response_item = {
                        "id": str(user.id),
                        "username": user.username,
                        "tier": user.tier,
                        "ip_address": user.ip_address,
                        "remaining_requests": settings.RateLimit.get_limit(user.tier),
                        "requests_today": 0,
                        "last_request": current_time.isoformat(),
                        "last_reset": current_time.isoformat()
                    }

                    # Create UserData for Redis
                    default_data = UserData(
                        id=str(user.id),
                        username=user.username,
                        tier=user.tier,
                        ip_address=user.ip_address,
                        remaining_requests=settings.RateLimit.get_limit(user.tier),
                        requests_today=0,
                        last_request=current_time,
                        last_reset=current_time
                    )

                    # Queue Redis update
                    redis_batch_tasks.append(
                        redis_manager.batch_processor.add_to_batch(
                            "set_user_data",
                            {"user_data": default_data},  # Pass as dict for clearer unpacking
                            priority=BatchPriority.MEDIUM
                        )
                    )

                users_data.append(response_item)

            except Exception as e:
                logger.error(f"Error processing user {user.id}: {e}", exc_info=True)
                continue

        # Wait for all batch operations to complete if there are any
        if redis_batch_tasks:
            try:
                await asyncio.gather(*redis_batch_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error in batch processing: {e}", exc_info=True)

        # Return response with proper structure
        return UsersResponse(users=users_data)

    except Exception as e:
        logger.error(f"Error getting users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    finally:
        await db.close()

@router.post("/admin/users", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@rate_limit(times=10, interval=15, period="minutes")
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    _: None = Depends(verify_master_key),
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

@router.post("/admin/sync-db", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
@rate_limit(times=10, interval=5, period="minutes")
async def sync_database(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    _: None = Depends(verify_master_key),
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