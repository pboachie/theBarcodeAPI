# /redis_manager.py

from redis.asyncio import Redis
from app.batch_processor import MultiLevelBatchProcessor
from contextlib import asynccontextmanager
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging
import pytz
import asyncio
import ipaddress

from app.config import settings
from app.schemas import BatchPriority, UserData, RedisConnectionStats
from app.models import User, Usage

from .lua_scripts import INCREMENT_USAGE_SCRIPT, GET_ALL_USER_DATA_SCRIPT

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.batch_processor = MultiLevelBatchProcessor(self)
        self.increment_usage_sha = None
        self.ip_cache = {}

    async def load_lua_scripts(self):
        """Load Lua scripts into Redis and store their SHAs"""
        self.increment_usage_sha = await self.redis.script_load(INCREMENT_USAGE_SCRIPT)

    async def start(self):
        """Start the batch processor and load Lua scripts"""
        logger.info("Starting batch processor...")
        await self.load_lua_scripts()
        await self.batch_processor.start()
        logger.info("Batch processor started.")

    async def stop(self):
        """Stop the batch processor"""
        logger.info("Stopping batch processor...")
        await self.batch_processor.stop()
        logger.info("Batch processor stopped.")

    @asynccontextmanager
    async def get_connection(self):
        """Context manager to handle Redis connections"""
        conn = await self.redis.connection_pool.get_connection("_")
        try:
            yield conn
        finally:
            await self.redis.connection_pool.release(conn)

    async def set_user_data(self, user_data: UserData):
        key = self._get_key(user_data.id, user_data.ip_address)
        try:
            async with self.get_connection():
                await self.redis.set(key, user_data.json(), ex=86400)
        except Exception as ex:
            logger.error(f"Error in set_user_data: {str(ex)}")

    async def get_user_data(
        self, user_id: Optional[int], ip_address: str
    ) -> Optional[UserData]:
        """Get user data from Redis"""
        try:
            key = self._get_key(user_id, ip_address)
            async with self.get_connection():
                data = await self.redis.get(key)
                if data:
                    return UserData.parse_raw(data)
                return None
        except Exception as ex:
            logger.error(f"Error fetching user data: {str(ex)}")
            return None

    def _get_key(
        self, user_id: Optional[int] = None, ip_address: Optional[str] = None
    ) -> str:
        """Generate Redis key for user data"""
        if user_id is None or user_id == -1:
            ip_str = self.ip_cache.get(ip_address)
            if ip_str is None:
                try:
                    ip = ipaddress.ip_address(ip_address)
                    ip_str = ip.compressed  # Normalize IP address
                    self.ip_cache[ip_address] = ip_str
                except ValueError:
                    logger.error(f"Invalid IP address: {ip_address}")
                    ip_str = ip_address  # Fallback to original IP address if invalid
            return f"ip:{ip_str}"
        return f"user_data:{user_id}"

    async def check_rate_limit(self, key: str) -> bool:
        """check rate limit for a given key"""
        result = await self.batch_processor.add_to_batch(
            "check_rate_limit", key, priority=BatchPriority.MEDIUM
        )

        return result

    async def increment_usage(
        self, user_id: Optional[int], ip_address: str
    ) -> Optional[UserData]:
        """Increment usage count and update user data using Lua script"""
        try:
            rate_limit = settings.RateLimit.get_limit("unauthenticated")
            current_time = datetime.now(pytz.utc).isoformat()
            user_id_str = str(user_id) if user_id else "-1"
            result = await self.redis.evalsha(
                self.increment_usage_sha,
                0,
                user_id_str,
                ip_address,
                rate_limit,
                current_time,
            )
            return UserData.parse_raw(result)
        except Exception as ex:
            logger.error(f"Error incrementing usage: {str(ex)}")
            return UserData(
                id=user_id if user_id else -1,
                username=f"ip:{ip_address}",
                ip_address=ip_address,
                tier="unauthenticated",
                remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
                requests_today=1,
                last_reset=datetime.now(pytz.utc),
            )

    async def get_all_user_keys(self):
        try:
            async with self.get_connection():
                return await self.redis.keys("user_data:*") + await self.redis.keys(
                    "ip:*"
                )
        except Exception as ex:
            logger.error(f"Error getting all user keys: {str(ex)}")
            return []

    async def reset_daily_usage(self):
        try:
            async with self.get_connection():
                keys = await self.get_all_user_keys()
                for key in keys:
                    user_data = await self.redis.get(key)
                    if user_data:
                        user_data = UserData.parse_raw(user_data)
                        user_data.requests_today = 0
                        await self.redis.set(key, user_data.json(), ex=86400)
        except Exception as ex:
            logger.error(f"Error resetting daily usage: {str(ex)}")

    async def sync_to_database(self, db: AsyncSession):
        """Synchronize all user data from Redis to the database"""
        try:
            # Execute the Lua script to retrieve all user data
            all_user_data = await self.redis.eval(GET_ALL_USER_DATA_SCRIPT, [], [])

            async with db.begin():
                for data in all_user_data:
                    key_type, key_id, user_data = data
                    if key_type == "ip":
                        user = await self.batch_processor.add_to_batch(
                            "get_user_data",
                            {"ip_address": key_id},
                            priority=BatchPriority.MEDIUM,
                        )
                    else:
                        user = await self.batch_processor.add_to_batch(
                            "get_user_data",
                            {"user_id": int(key_id)},
                            priority=BatchPriority.MEDIUM,
                        )

                    if user:
                        usage = Usage(
                            user_id=user.id,
                            requests_today=user.requests_today,
                            last_reset=user.last_reset,
                        )
                        db.add(usage)

                await db.commit()
            logger.info("Redis data synced to database")
        except Exception as ex:
            logger.error(f"Error syncing Redis data to database: {str(ex)}")
            raise

    async def sync_all_username_mappings(self, db: AsyncSession):
        try:
            async with self.get_connection(), db.begin():
                result = await db.execute(select(User))
                users = result.scalars().all()

                for user in users:
                    await self.set_username_to_id_mapping(user.username, user.id)
                    requests_limit = settings.RateLimit.get_limit(user.tier)

                    user_requests = await self.redis.get(
                        f"user_data:{user.id}:requests_today"
                    )
                    user_requests = (
                        int(user_requests)
                        if user_requests and int(user_requests) >= 0
                        else 0
                    )

                    user_data = UserData(
                        id=user.id,
                        username=user.username,
                        ip_address=user.ip_address,
                        tier=user.tier,
                        remaining_requests=requests_limit,
                        requests_today=user_requests,
                        last_reset=datetime.now(),
                    )
                    await self.set_user_data(user_data)

        except Exception as ex:
            logger.error(f"Error syncing username mappings: {str(ex)}")
            raise

    async def get_user_data(
        self, user_id: Optional[int], ip_address: str
    ) -> Optional[UserData]:
        """Get user data from Redis"""
        try:
            key = self._get_key(user_id, ip_address)
            async with self.get_connection():
                data = await self.redis.get(key)

                if data:
                    return UserData.parse_raw(data)

                # If no data found, create default user data
                return UserData(
                    id=user_id if user_id else -1,
                    username=f"ip:{ip_address}",
                    ip_address=ip_address,
                    tier="unauthenticated",
                    remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
                    requests_today=0,
                    last_reset=datetime.now(pytz.utc),
                )

        except Exception as ex:
            logger.error(f"Error fetching user data: {str(ex)}")
            # Return default user data in case of error
            return UserData(
                id=user_id if user_id else -1,
                username=f"ip:{ip_address}",
                ip_address=ip_address,
                tier="unauthenticated",
                remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
                requests_today=0,
                last_reset=datetime.now(pytz.utc),
            )

    async def get_user_data_by_ip(self, ip_address: str) -> Optional[UserData]:
        try:
            async with self.get_connection():
                user_data = await self.redis.get(f"ip:{ip_address}")
                if user_data:
                    user_data = UserData.parse_raw(user_data)
                    return await self.get_user_data(
                        user_id=int(user_data.id), ip_address=user_data.ip_address
                    )
                else:
                    return UserData(
                        id=-1,
                        username=f"ip:{ip_address}",
                        tier="unauthenticated",
                        ip_address=ip_address,
                        remaining_requests=settings.RateLimit.get_limit(
                            "unauthenticated"
                        ),
                        requests_today=0,
                        last_reset=datetime.now(pytz.utc),
                    )
        except Exception as ex:
            logger.error(f"Error fetching user data by IP: {str(ex)}")
        return None

    async def add_active_token(self, user_id: int, token: str, expire_time: int = 3600):
        try:
            async with self.get_connection():
                key = f"user_data:{user_id}:active_token"
                await self.redis.set(key, token, ex=expire_time)
        except Exception as ex:
            logger.error(f"Error adding active token: {str(ex)}")

    async def get_active_token(self, user_id: int) -> Optional[str]:
        try:
            async with self.get_connection():
                key = f"user_data:{user_id}:active_token"
                token = await self.redis.get(key)
                return token if token else None
        except Exception as ex:
            logger.error(f"Error getting active token: {str(ex)}")
            return None

    async def remove_active_token(self, user_id: int):
        try:
            async with self.get_connection():
                key = f"user_data:{user_id}:active_token"
                await self.redis.delete(key)
        except Exception as ex:
            logger.error(f"Error removing active token: {str(ex)}")

    async def is_token_active(self, user_id: int, token: str) -> bool:
        try:
            stored_token = await self.get_active_token(user_id)
            return stored_token == token
        except Exception as ex:
            logger.error(f"Error checking if token is active: {str(ex)}")
        return False

    async def set_username_to_id_mapping(self, username: str, user_id: int):
        try:
            await self.redis.set(f"user_data:{username}:username", user_id)
        except Exception as ex:
            logger.error(f"Error setting username to ID mapping: {str(ex)}")

    async def check_redis(self) -> str:
        try:
            async with self.get_connection():
                await self.redis.ping()
                logger.debug("Redis health check successful")
                return "ok"
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return "error"

    async def get_connection_stats(self) -> RedisConnectionStats:
        try:
            async with self.get_connection():
                info = await self.redis.info("clients")
                return RedisConnectionStats(
                    connected_clients=info["connected_clients"],
                    blocked_clients=info["blocked_clients"],
                    tracking_clients=info.get("tracking_clients", 99999),
                )
        except Exception as ex:
            logger.error(f"Error getting connection stats: {str(ex)}")
            return RedisConnectionStats(
                connected_clients=99999, blocked_clients=99999, tracking_clients=99999
            )

    # async def clean_expired_tokens(self):
    #     try:
    #         all_user_keys = await self.redis.keys("user:*:active_tokens")
    #         for key in all_user_keys:
    #             active_tokens = await self.redis.smembers(key)
    #             for token in active_tokens:
    #                 # Check if token is expired (you may need to decode and check the expiration)
    #                 # For simplicity, let's assume tokens older than 24 hours are expired. Need to change this later.
    #                 token_added_time = await self.redis.zscore(f"{key}:timestamps", token)
    #                 if token_added_time and datetime.now().timestamp() - token_added_time > 86400:
    #                     await self.redis.srem(key, token)
    #                     await self.redis.zrem(f"{key}:timestamps", token)
    #     except Exception as ex:
    #         logger.error(f"Error cleaning expired tokens: {str(ex)}")
