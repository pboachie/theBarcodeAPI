# app/api/admin.py

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models import User
from app.dependencies import get_current_user, get_redis_manager
from app.security import get_password_hash, validate_password_strength, verify_master_key
from app.config import settings
from app.schemas import BatchPriority, UserCreate, UsersResponse, UserCreatedResponse, UserData
from app.rate_limiter import rate_limit
from app.redis_manager import RedisManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def include_in_schema() -> bool:
    return settings.ENVIRONMENT != "production"

@router.get("/admin/users", response_model=UsersResponse, include_in_schema=include_in_schema())
@rate_limit(times=75, interval=15, period="minutes")
async def get_users(
    request: Request,
    redis_manager: RedisManager = Depends(get_redis_manager),
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(get_current_user),
    _: None = Depends(verify_master_key)
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

        # Log the user and IP attempting to get users
        logger.info(f"User data requested by {current_user.username} from {current_user.ip_address}")

        async with db.begin():
            result = await db.execute(select(User))
            db_users = result.scalars().all()

        for user in db_users:
            try:
                # Get user data from Redis using batch processor
                user_data = await redis_manager.batch_processor.add_to_batch(
                    "get_user_data",
                    {"user_id": user.id},
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
                        "remaining_requests": settings.RateLimit.get_limit(str(user.tier)),
                        "requests_today": 0,
                        "last_request": current_time.isoformat(),
                        "last_reset": current_time.isoformat()
                    }

                    # Create UserData for Redis
                    default_data = UserData(
                        id=str(user.id),
                        username=str(user.username),
                        tier=str(user.tier),
                        ip_address=str(user.ip_address),
                        remaining_requests=settings.RateLimit.get_limit(str(user.tier)),
                        requests_today=0,
                        last_request=current_time,
                        last_reset=current_time
                    )

                    # Queue Redis update
                    redis_batch_tasks.append(
                        redis_manager.batch_processor.add_to_batch(
                            "set_user_data",
                            {"user_data": default_data},
                            priority=BatchPriority.MEDIUM
                        )
                    )

                users_data.append(response_item)

            except Exception as e:
                logger.error(f"Error processing user {user.id}: {e}", exc_info=True)
                continue

        # Wait for all batch operations to complete if there are any
        if redis_batch_tasks:
            results = await asyncio.gather(*redis_batch_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in batch processing: {result}", exc_info=True)
        try:
            return UsersResponse(users=users_data)
        except ValidationError as e:
            logger.error(f"Validation error when creating UsersResponse: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Data validation error"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal Server Error"
            )
    except Exception as e:
        logger.error(f"Error getting users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    finally:
        try:
            await db.close()
        except Exception as e:
            logger.error(f"Error closing the database session: {e}", exc_info=True)

@router.post("/admin/users", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED, include_in_schema=include_in_schema())
@rate_limit(times=10, interval=15, period="minutes")
async def create_user(
    request: Request,
    user: UserCreate,
    redis_manager: RedisManager = Depends(get_redis_manager),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_master_key)
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
        current_user (User): The current authenticated user.
        _ (None): Dependency to verify the master key.
        __ (bool): Dependency to apply rate limiting.
        redis_manager (RedisManager): The Redis manager dependency.

    Returns:
        UserCreatedResponse: A response object containing a success message, the new user's ID, tier, and username.

    Raises:
        HTTPException: If the username is already registered or if there is an error during user creation.
    """
    try:

        # Log the user and IP attempting the creation
        logger.info(f"User creation requested by {current_user.username} from {current_user.ip_address}")

        async with db.begin():
            # Check if user already exists
            result = await db.execute(select(User).filter(User.username == user.username))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )

            validate_password_strength(user.password)
            hashed_password = get_password_hash(user.password)
            new_user = User(username=user.username, hashed_password=hashed_password, tier=user.tier.value)
            db.add(new_user)
            await db.flush()
            await db.refresh(new_user) # Refresh the user object to get the ID

        # Initialize user data in Redis
        current_time = datetime.now()
        user_data = UserData(
            id=str(new_user.id),
            username=str(new_user.username),
            ip_address=None,
            tier=str(new_user.tier),
            remaining_requests=settings.RateLimit.get_limit(str(new_user.tier)),
            requests_today=0,
            last_reset=current_time,
            last_request=current_time
        )
        await redis_manager.set_user_data(user_data)
        await redis_manager.set_username_to_id_mapping(str(new_user.username), str(new_user.id))

        return UserCreatedResponse(
            message="User created successfully",
            user_id=str(new_user.id),
            tier=str(new_user.tier),
            username=str(new_user.username)
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.post("/admin/sync-db", status_code=status.HTTP_202_ACCEPTED, include_in_schema=include_in_schema())
@rate_limit(times=10, interval=5, period="minutes")
async def sync_database(
    request: Request,
    redis_manager: RedisManager = Depends(get_redis_manager),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_master_key),
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
    # Attempt database sync
    try:

        # Log the user and IP attempting the sync
        logger.info(f"Database sync requested by {current_user.username} from {current_user.ip_address}")

        try:
            await redis_manager.sync_redis_to_db(db)
            await db.commit()

            return JSONResponse(
                content={"message": "Database sync completed successfully"},
                status_code=status.HTTP_200_OK
            )
        except Exception as sync_error:
            logger.error(f"Sync error: {str(sync_error)}", exc_info=True)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database sync failed: {str(sync_error)}"
            )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        await db.close()