from redis.asyncio import Redis
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging
import pytz
import asyncio
import ipaddress
import gc
from enum import Enum
from collections import defaultdict
import time

from app.config import settings
from app.schemas import BatchPriority, UserData, RedisConnectionStats
from app.models import User, Usage
from app.batch_processor import MultiLevelBatchProcessor
from .lua_scripts import INCREMENT_USAGE_SCRIPT, GET_ALL_USER_DATA_SCRIPT

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.batch_processor = MultiLevelBatchProcessor(self)
        self.increment_usage_sha = None
        self.ip_cache = {}

    @asynccontextmanager
    async def get_connection(self):
        """Context manager to handle Redis connections with proper cleanup"""
        conn = await self.redis.connection_pool.get_connection("_")
        try:
            yield conn
        finally:
            await self.redis.connection_pool.release(conn)

    @asynccontextmanager
    async def get_pipeline(self):
        """Context manager for Redis pipeline operations"""
        pipe = self.redis.pipeline()
        try:
            yield pipe
            await pipe.execute()
        finally:
            await pipe.reset()

    async def load_lua_scripts(self):
        """Load Lua scripts into Redis and store their SHAs"""
        try:
            self.increment_usage_sha = await self.redis.script_load(INCREMENT_USAGE_SCRIPT)
            logger.info("Lua scripts loaded successfully")
        except Exception as ex:
            logger.error(f"Error loading Lua scripts: {str(ex)}")
            raise

    async def start(self):
        """Initialize and start the Redis manager"""
        logger.info("Starting Redis manager...")
        await self.load_lua_scripts()
        await self.batch_processor.start()
        logger.info("Redis manager started successfully")

    async def stop(self):
        """Gracefully shutdown the Redis manager"""
        logger.info("Stopping Redis manager...")
        try:
            await self.batch_processor.stop()
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            self.ip_cache.clear()
            gc.collect()
            logger.info("Redis manager stopped successfully")
        except Exception as ex:
            logger.error(f"Error during Redis manager shutdown: {str(ex)}")

    async def process_batch_operation(self, operation: str, items: List[Tuple[Any, str]], pipe, pending_results):
        """Handle all Redis operations for batch processing"""
        try:
            # Map operations to their handlers
            operation_handlers = {
                "get_user_data": self._process_get_user_data,
                "set_user_data": self._process_set_user_data,
                "increment_usage": self._process_increment_usage,
                "check_rate_limit": self._process_check_rate_limit,
                "is_token_active": self._process_token_checks,
                "get_active_token": self._process_get_tokens,
                "reset_daily_usage": self._process_reset_daily_usage,
                "set_username_mapping": self._process_username_mappings,
                "get_user_data_by_ip": self._process_get_user_data_by_ip
            }

            handler = operation_handlers.get(operation)
            if handler:
                await handler(items, pipe, pending_results)
            else:
                logger.warning(f"Unknown operation type: {operation}")
                for _, batch_id in items:
                    if batch_id in pending_results:
                        future = pending_results[batch_id]
                        if not future.done():
                            future.set_result(self.get_default_value(operation))
        except Exception as ex:
            logger.error(f"Error in process_batch_operation {operation}: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(self.get_default_value(operation))

    async def _process_set_user_data(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of set user data operations"""
        try:
            for (user_data,), batch_id in items:
                key = self._get_key(user_data.id, user_data.ip_address)
                current_time = datetime.now(pytz.utc)

                mapping = {
                    "id": str(user_data.id),
                    "ip_address": str(user_data.ip_address),
                    "username": str(user_data.username),
                    "tier": str(user_data.tier),
                    "requests_today": str(user_data.requests_today),
                    "remaining_requests": str(user_data.remaining_requests),
                    "last_request": user_data.last_request.isoformat() if user_data.last_request else current_time.isoformat(),
                    "last_reset": user_data.last_reset.isoformat() if user_data.last_reset else current_time.isoformat()
                }

                pipe.hset(key, mapping=mapping)
                pipe.expire(key, 86400)

            results = await pipe.execute()
            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(bool(results[i * 2]))  # Use hset result

        except Exception as ex:
            logger.error(f"Error in _process_set_user_data: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(False)

    async def _process_get_user_data(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of get_user_data operations"""
        try:
            for (ip_address,), batch_id in items:
                key = self._get_key(None, ip_address)
                pipe.hgetall(key)

            results = await pipe.execute()

            for i, ((ip_address,), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    if results[i]:
                        try:
                            current_time = datetime.now(pytz.utc)
                            defaults = {
                                "id": -1,
                                "ip_address": ip_address,
                                "username": f"ip:{ip_address}",
                                "tier": "unauthenticated",
                                "requests_today": 0,
                                "remaining_requests": settings.RateLimit.get_limit("unauthenticated"),
                                "last_request": current_time,
                                "last_reset": current_time
                            }

                            user_data_dict = self._parse_redis_hash(results[i], defaults)
                            future.set_result(UserData(**user_data_dict))
                        except Exception as ex:
                            logger.error(f"Error parsing user data hash: {ex}")
                            future.set_result(self.create_default_user_data(ip_address))
                    else:
                        future.set_result(self.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error in get_user_data batch: {str(ex)}")
            for (ip_address,), batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(self.create_default_user_data(ip_address))

    async def _process_increment_usage(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of increment usage operations"""
        try:
            current_time = datetime.now(pytz.utc).isoformat()

            for (user_id, ip_address), batch_id in items:
                key = self._get_key(user_id, ip_address)
                pipe.evalsha(
                    self.increment_usage_sha,
                    1,  # number of keys
                    key,  # key
                    str(user_id if user_id else -1),
                    str(ip_address),
                    str(settings.RateLimit.get_limit("unauthenticated")),
                    current_time
                )

            results = await pipe.execute()

            for i, ((_, ip_address), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    try:
                        if results[i]:
                            data = dict(zip(results[i][::2], results[i][1::2]))
                            defaults = {
                                "id": -1,
                                "ip_address": ip_address,
                                "username": f"ip:{ip_address}",
                                "tier": "unauthenticated",
                                "requests_today": 0,
                                "remaining_requests": settings.RateLimit.get_limit("unauthenticated"),
                                "last_request": current_time,
                                "last_reset": current_time
                            }
                            user_data_dict = self._parse_redis_hash(data, defaults)
                            future.set_result(UserData(**user_data_dict))
                        else:
                            future.set_result(self.create_default_user_data(ip_address))
                    except Exception as ex:
                        logger.error(f"Error parsing increment usage result: {ex}")
                        future.set_result(self.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error in _process_increment_usage: {ex}")
            for (_, ip_address), batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(self.create_default_user_data(ip_address))

    async def _process_check_rate_limit(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of rate limit checks"""
        try:
            current_time = datetime.now(pytz.utc).isoformat()

            for (key,), batch_id in items:
                pipe.evalsha(
                    self.rate_limit_sha,
                    1,  # number of keys
                    key,
                    86400,  # window size
                    settings.RateLimit.get_limit("unauthenticated"),
                    current_time
                )

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(results[i] != -1)

        except Exception as ex:
            logger.error(f"Error in _process_check_rate_limit: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(False)

    async def _process_token_checks(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of token checks"""
        try:
            for (user_id, token), batch_id in items:
                pipe.hget(f"user_data:{user_id}", "active_token")

            results = await pipe.execute()

            for i, ((_, token), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    result = results[i].decode() if results[i] else None
                    future.set_result(result == token)

        except Exception as ex:
            logger.error(f"Error in _process_token_checks: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(False)

    async def _process_get_tokens(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of token retrievals"""
        try:
            for (user_id,), batch_id in items:
                pipe.hget(f"user_data:{user_id}", "active_token")

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    result = results[i].decode() if results[i] else None
                    future.set_result(result)

        except Exception as ex:
            logger.error(f"Error in _process_get_tokens: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(None)

    async def _process_reset_daily_usage(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of reset daily usage operations"""
        try:
            for (key,), batch_id in items:
                key_type = await self.redis.type(key)

                if key_type == b'hash':
                    pipe.hset(key, mapping={
                        "requests_today": "0",
                        "remaining_requests": str(settings.RateLimit.get_limit("unauthenticated"))
                    })
                elif key.startswith("ip:") or key.startswith("user_data:"):
                    # Convert to hash if not already
                    pipe.hset(key, mapping={
                        "requests_today": "0",
                        "remaining_requests": str(settings.RateLimit.get_limit("unauthenticated"))
                    })
                    pipe.expire(key, 86400)
                else:
                    logger.warning(f"Invalid key type for {key}, skipping")
                    continue

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(True)

        except Exception as ex:
            logger.error(f"Error in _process_reset_daily_usage: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(False)

    async def _process_username_mappings(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of username mapping operations"""
        try:
            for (username, user_id), batch_id in items:
                key = self._get_key(user_id, None)
                pipe.hset(key, "username", username)

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(bool(results[i]))

        except Exception as ex:
            logger.error(f"Error in _process_username_mappings: {ex}")
            for _, batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(False)

    async def _process_get_user_data_by_ip(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of get user data by IP operations"""
        try:
            for (ip_address,), batch_id in items:
                key = self._get_key(None, ip_address)
                pipe.hgetall(key)

            results = await pipe.execute()

            for i, ((ip_address,), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    if results[i]:
                        try:
                            current_time = datetime.now(pytz.utc)
                            defaults = {
                                "id": -1,
                                "ip_address": ip_address,
                                "username": f"ip:{ip_address}",
                                "tier": "unauthenticated",
                                "requests_today": 0,
                                "remaining_requests": settings.RateLimit.get_limit("unauthenticated"),
                                "last_request": current_time,
                                "last_reset": current_time
                            }
                            user_data_dict = self._parse_redis_hash(results[i], defaults)
                            future.set_result(UserData(**user_data_dict))
                        except Exception:
                            future.set_result(self.create_default_user_data(ip_address))
                    else:
                        future.set_result(self.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error in _process_get_user_data_by_ip: {ex}")
            for (ip_address,), batch_id in items:
                if batch_id in pending_results:
                    future = pending_results[batch_id]
                    if not future.done():
                        future.set_result(self.create_default_user_data(ip_address))

    def get_default_value(self, operation: str, item: Any = None) -> Any:
        """Get default values for operations"""
        defaults = {
            "check_rate_limit": False,
            "is_token_active": False,
            "get_active_token": None,
            "set_user_data": False,
            "set_username_mapping": False,
            "reset_daily_usage": False
        }
        if operation in ["get_user_data", "get_user_data_by_ip", "increment_usage"]:
            ip_address = self._extract_ip_address(item)
            return self.create_default_user_data(ip_address)
        return defaults.get(operation, None)

    async def _batch_get_user_data(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of get_user_data operations using hashes"""
        try:
            for (ip_address,), batch_id in items:
                key = self.redis_manager._get_key(None, ip_address)
                pipe.hgetall(key)

            results = await pipe.execute()

            for i, ((ip_address,), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    if results[i]:
                        try:
                            current_time = datetime.now(pytz.utc)
                            data = results[i]

                            # Handle fields more safely, with proper type conversion
                            user_data_dict = {
                                "id": int(data[b"id"].decode()) if b"id" in data else -1,
                                "ip_address": data[b"ip_address"].decode() if b"ip_address" in data else ip_address,
                                "username": data[b"username"].decode() if b"username" in data else f"ip:{ip_address}",
                                "tier": data[b"tier"].decode() if b"tier" in data else "unauthenticated",
                                "requests_today": int(data[b"requests_today"].decode()) if b"requests_today" in data else 0,
                                "remaining_requests": int(data[b"remaining_requests"].decode()) if b"remaining_requests" in data else settings.RateLimit.get_limit("unauthenticated"),
                                "last_request": datetime.fromisoformat(data[b"last_request"].decode()) if b"last_request" in data else current_time,
                                "last_reset": datetime.fromisoformat(data[b"last_reset"].decode()) if b"last_reset" in data else current_time
                            }
                            user_data = UserData(**user_data_dict)
                            future.set_result(user_data)
                        except Exception as ex:
                            logger.error(f"Error parsing user data hash: {ex}")
                            future.set_result(self.redis_manager.create_default_user_data(ip_address))
                    else:
                        future.set_result(self.redis_manager.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error in get_user_data batch: {str(ex)}")
            for (ip_address,), batch_id in items:
                self._cleanup_future(batch_id, self.redis_manager.create_default_user_data(ip_address))

    async def _batch_set_user_data(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of set user data operations using hashes"""
        try:
            for (user_data,), batch_id in items:
                key = self.redis_manager._get_key(user_data.id, user_data.ip_address)
                # Convert UserData to hash fields
                mapping = {
                    "ip_address": user_data.ip_address,
                    "requests_today": str(user_data.requests_today),
                    "remaining_requests": str(user_data.remaining_requests),
                    "last_request": user_data.last_request.isoformat() if user_data.last_request else datetime.now(pytz.utc).isoformat()
                }
                pipe.hset(key, mapping=mapping)
                pipe.expire(key, 86400)  # Set expiration

            results = await pipe.execute()

            # Process results in pairs (hset and expire commands)
            for i, (_, batch_id) in enumerate(items):
                self._cleanup_future(batch_id, bool(results[i * 2]))  # Use hset result

        except Exception as ex:
            logger.error(f"Error in set_user_data batch: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)

    async def _batch_increment_usage(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of increment_usage operations using hash fields"""
        try:
            for (user_id, ip_address), batch_id in items:
                key = self.redis_manager._get_key(user_id, ip_address)
                current_time = datetime.now(pytz.utc).isoformat()

                # Use Lua script for atomic increment
                pipe.evalsha(
                    self.redis_manager.increment_usage_sha,
                    1,  # number of keys
                    key,  # key
                    str(user_id if user_id else -1),
                    str(ip_address),
                    str(settings.RateLimit.get_limit("unauthenticated")),
                    current_time
                )

            results = await pipe.execute()

            for i, ((_, ip_address), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    try:
                        if results[i]:
                            # Convert hash results to dict for easier processing
                            data = dict(zip(results[i][::2], results[i][1::2]))
                            user_data_dict = {
                                "id": int(data[b"id"].decode()) if b"id" in data else -1,
                                "ip_address": data[b"ip_address"].decode() if b"ip_address" in data else ip_address,
                                "username": data[b"username"].decode() if b"username" in data else f"ip:{ip_address}",
                                "tier": data[b"tier"].decode() if b"tier" in data else "unauthenticated",
                                "requests_today": int(data[b"requests_today"].decode()) if b"requests_today" in data else 0,
                                "remaining_requests": int(data[b"remaining_requests"].decode()) if b"remaining_requests" in data else settings.RateLimit.get_limit("unauthenticated"),
                                "last_request": datetime.fromisoformat(data[b"last_request"].decode()) if b"last_request" in data else datetime.now(pytz.utc),
                                "last_reset": datetime.fromisoformat(data[b"last_reset"].decode()) if b"last_reset" in data else datetime.now(pytz.utc)
                            }
                            user_data = UserData(**user_data_dict)
                            future.set_result(user_data)
                        else:
                            future.set_result(self.redis_manager.create_default_user_data(ip_address))
                    except Exception as ex:
                        logger.error(f"Error parsing increment usage result: {ex}")
                        future.set_result(self.redis_manager.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error in increment_usage batch: {str(ex)}")
            for (_, ip_address), batch_id in items:
                self._cleanup_future(batch_id, self.redis_manager.create_default_user_data(ip_address))

    async def _batch_check_rate_limit(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of rate limit checks using hash fields"""
        try:
            current_time = datetime.now(pytz.utc).isoformat()
            for (key,), batch_id in items:
                pipe.evalsha(
                    self.redis_manager.rate_limit_sha,
                    1,  # number of keys
                    key,
                    86400,  # window size
                    settings.RateLimit.get_limit("unauthenticated"),
                    current_time
                )

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(results[i] != -1)  # Check if we hit the rate limit
        except Exception as ex:
            logger.error(f"Error in check_rate_limit batch: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)

    async def _batch_token_checks(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of token checks using hash fields"""
        try:
            for (user_id, token), batch_id in items:
                pipe.hget(f"user_data:{user_id}", "active_token")

            results = await pipe.execute()

            for i, ((_, token), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    result = results[i].decode() if results[i] else None
                    future.set_result(result == token)
        except Exception as ex:
            logger.error(f"Error in token checks batch: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)

    async def _batch_get_tokens(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of token retrievals using hash fields"""
        try:
            for (user_id,), batch_id in items:
                pipe.hget(f"user_data:{user_id}", "active_token")

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    result = results[i].decode() if results[i] else None
                    future.set_result(result)
        except Exception as ex:
            logger.error(f"Error in get tokens batch: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, None)

    async def _batch_reset_daily_usage(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of reset daily usage operations"""
        try:
            keys = [key for (key,), _ in items]
            # Use Redis pipeline to reset usage counts
            for key in keys:
                key_type = await self.redis_manager.redis.type(key)
                if key_type == b'hash':
                    pipe.hset(key, mapping={
                        "requests_today": 0,
                        "remaining_requests": settings.RateLimit().get_limit("unauthenticated")  # Adjust tier as needed
                    })
                elif key.startswith("ip:"):
                    logger.info(f"Converting key {key} to a hash type")
                    # Retrieve existing value if needed
                    # Delete the existing key
                    await self.redis_manager.redis.delete(key)
                    # Set as hash with default values
                    pipe.hset(key, mapping={
                        "requests_today": 0,
                        "remaining_requests": settings.RateLimit().get_limit("unauthenticated")
                    })
                else:
                    logger.warning(f"Key {key} is not a hash and does not match pattern, deleting key and skipping HSET operation")
                    await self.redis_manager.redis.delete(key)
            await pipe.execute()
            # Resolve futures if you are tracking them
            for _, batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(True)
        except Exception as ex:
            logger.error(f"Error in _batch_reset_daily_usage: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)
        finally:
            await pipe.reset()

    async def _batch_username_mappings(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of username mapping operations using hash fields"""
        try:
            for (username, user_id), batch_id in items:
                pipe.hset(f"user_data:{user_id}", "username", username)

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(bool(results[i]))
        except Exception as ex:
            logger.error(f"Error in username mapping batch: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)

    async def _batch_get_user_data_by_ip(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of get user data by IP operations using hash fields"""
        try:
            for (ip_address,), batch_id in items:
                key = f"ip:{ip_address}"
                pipe.hgetall(key)

            results = await pipe.execute()

            pipe.reset()
            secondary_keys = []

            for i, ((ip_address,), batch_id) in enumerate(items):
                if results[i]:
                    try:
                        # Convert hash results to UserData
                        user_data_dict = {
                            "ip_address": ip_address,
                            "requests_today": int(results[i].get(b"requests_today", 0)),
                            "remaining_requests": int(results[i].get(b"remaining_requests", settings.RateLimit.get_limit("unauthenticated"))),
                            "last_request": results[i].get(b"last_request", datetime.now(pytz.utc).isoformat()).decode()
                        }
                        user_data = UserData(**user_data_dict)
                        future = self.pending_results.get(batch_id)
                        if future and not future.done():
                            future.set_result(user_data)
                    except Exception:
                        self._cleanup_future(batch_id, self.redis_manager.create_default_user_data(ip_address))
                else:
                    self._cleanup_future(batch_id, self.redis_manager.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error in get_user_data_by_ip batch: {str(ex)}")
            for (ip_address,), batch_id in items:
                self._cleanup_future(batch_id, self.redis_manager.create_default_user_data(ip_address))

    async def _batch_operation_group(self, operation: str, items: List[Tuple[Any, str]], pipe):
        """Process a group of similar operations"""
        try:
            # Create new pipeline for each operation group
            async with self.get_pipeline() as operation_pipe:
                if operation == "get_user_data":
                    await self._batch_get_user_data(items, operation_pipe)
                elif operation == "increment_usage":
                    await self._batch_increment_usage(items, operation_pipe)
                elif operation == "check_rate_limit":
                    await self._batch_check_rate_limit(items, operation_pipe)
                elif operation == "is_token_active":
                    await self._batch_token_checks(items, operation_pipe)
                elif operation == "get_active_token":
                    await self._batch_get_tokens(items, operation_pipe)
                elif operation == "set_user_data":
                    await self._batch_set_user_data(items, operation_pipe)
                elif operation == "reset_daily_usage":
                    await self._batch_reset_daily_usage(items, operation_pipe)
                elif operation == "set_username_mapping":
                    await self._batch_username_mappings(items, operation_pipe)
                elif operation == "get_user_data_by_ip":
                    await self._batch_get_user_data_by_ip(items, operation_pipe)
                else:
                    logger.warning(f"Unknown operation type: {operation}")
                    for _, batch_id in items:
                        self._cleanup_future(batch_id, self._get_default_value(operation))

        except Exception as ex:
            logger.error(f"Error processing operation {operation}: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, self._get_default_value(operation))

    async def _batch_batches(self):
        """Main batch processing loop"""
        logger.info(f"Starting batch processor with interval {self.interval:.3f}s")
        while not self._stopping:
            try:
                sleep_time = min(self.interval / 4, 0.05) if self.interval > 0.05 else 0.01
                await asyncio.sleep(sleep_time)

                if not self.batch or self.processing:
                    continue

                current_time = time.time()
                if current_time - self.last_batch_time >= self.interval:
                    async with self._processing_lock:
                        await self._batch_current_batch()

            except Exception as ex:
                logger.error(f"Error in _batch_batches: {str(ex)}")
                await asyncio.sleep(0.01)

    async def _batch_current_batch(self):
        """Process the current batch of operations with error handling"""
        if not self.batch:
            return

        self.processing = True
        current_batch = []
        start_time = time.time()

        try:
            async with self._batch_lock:
                current_batch = self.batch.copy()
                self.batch = []
                self.current_batch_id += 1

            # Group operations for efficient processing
            operation_groups = self._group_operations(current_batch)

            # Process each operation group using Redis pipeline where possible
            async with self.redis_manager.get_pipeline() as pipe:
                for operation, items in operation_groups.items():
                    await self._batch_operation_group(operation, items, pipe)

            process_time = (time.time() - start_time) * 1000
            logger.debug(f"Batch processed in {process_time:.2f}ms")

        except Exception as ex:
            logger.error(f"Error processing batch: {str(ex)}\n{traceback.format_exc()}")
            self._handle_batch_error(current_batch)
        finally:
            self.processing = False
            self.last_batch_time = time.time()

    async def _batch_operation_group(self, operation: str, items: List[Tuple[Any, str]], pipe):
        """Process a group of similar operations"""
        processor = getattr(self, f"_batch_{operation}", None)
        if processor:
            await processor(items, pipe)
        else:
            logger.warning(f"Unknown operation type: {operation}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, None)

    async def _batch_pipeline_operation(self, operation: str, items: List[Tuple[Any, str]], pipe):
        """Process operations that can use Redis pipeline"""
        try:
            for item, batch_id in items:
                getattr(self, f"_add_to_pipeline_{operation}")(item, pipe)

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                self._cleanup_future(batch_id, results[i])
        except Exception as ex:
            logger.error(f"Error in pipeline operation {operation}: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, self._get_default_value(operation))

    def _get_key(self, user_id: Optional[int] = None, ip_address: Optional[str] = None) -> str:
        """Generate normalized Redis key for user data"""
        if user_id is None or user_id == -1:
            ip_str = self.ip_cache.get(ip_address)
            if ip_str is None:
                try:
                    ip = ipaddress.ip_address(ip_address)
                    ip_str = ip.compressed
                    self.ip_cache[ip_address] = ip_str
                except ValueError:
                    logger.error(f"Invalid IP address: {ip_address}")
                    ip_str = ip_address
            return f"ip:{ip_str}"
        return f"user_data:{user_id}"

    def _extract_ip_address(self, item: Any) -> str:
        """Extract IP address from different item types"""
        if isinstance(item, tuple):
            return str(item[1] if len(item) > 1 else item[0])
        elif isinstance(item, dict):
            return item.get('ip_address', "unknown")
        return str(item)

    async def set_user_data(self, user_data: UserData) -> bool:
        """Set user data directly using hash fields"""
        try:
            key = self._get_key(user_data.id, user_data.ip_address)
            current_time = datetime.now(pytz.utc)

            mapping = {
                "id": str(user_data.id),
                "ip_address": str(user_data.ip_address),
                "username": str(user_data.username),
                "tier": str(user_data.tier),
                "requests_today": str(user_data.requests_today),
                "remaining_requests": str(user_data.remaining_requests),
                "last_request": user_data.last_request.isoformat() if user_data.last_request else current_time.isoformat(),
                "last_reset": user_data.last_reset.isoformat() if user_data.last_reset else current_time.isoformat()
            }

            async with self.get_pipeline() as pipe:
                pipe.hset(key, mapping=mapping)
                pipe.expire(key, 86400)  # Set expiration for 24 hours
                results = await pipe.execute()
                return bool(results[0])

        except Exception as ex:
            logger.error(f"Error in set_user_data: {str(ex)}")
            return False

    async def get_user_data(self, user_id: Optional[int], ip_address: str) -> UserData:
        """Get user data from Redis with fallback to default"""
        try:
            key = self._get_key(user_id, ip_address)
            async with self.get_connection():
                data = await self.redis.hgetall(key)
                if data:
                    try:
                        current_time = datetime.now(pytz.utc)
                        defaults = {
                            "id": -1,
                            "ip_address": ip_address,
                            "username": f"ip:{ip_address}",
                            "tier": "unauthenticated",
                            "requests_today": 0,
                            "remaining_requests": settings.RateLimit.get_limit("unauthenticated"),
                            "last_request": current_time,
                            "last_reset": current_time
                        }

                        user_data_dict = {}
                        for key, default in defaults.items():
                            byte_key = key.encode()
                            if byte_key in data:
                                value = data[byte_key]
                                if isinstance(default, int):
                                    user_data_dict[key] = int(value.decode())
                                elif isinstance(default, datetime):
                                    user_data_dict[key] = datetime.fromisoformat(value.decode())
                                else:
                                    user_data_dict[key] = value.decode()
                            else:
                                user_data_dict[key] = default

                        return UserData(**user_data_dict)
                    except Exception as ex:
                        logger.error(f"Error parsing Redis hash data: {ex}")
                        return self.create_default_user_data(ip_address)
                return self.create_default_user_data(ip_address)
        except Exception as ex:
            logger.error(f"Error fetching user data: {str(ex)}")
            return self.create_default_user_data(ip_address)

    def _parse_redis_hash(self, data: Dict[bytes, bytes], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Redis hash data with proper type conversion and error handling.

        Args:
            data: Redis hash response (bytes keys and values)
            defaults: Default values with expected types

        Returns:
            Dict with properly converted values
        """
        result = {}
        try:
            for key, default in defaults.items():
                byte_key = key.encode()

                # Get value from Redis data or use default
                if byte_key in data:
                    value = data[byte_key]
                    try:
                        if isinstance(default, int):
                            # Handle integer conversion
                            result[key] = int(value.decode().strip() or 0)
                        elif isinstance(default, datetime):
                            # Handle datetime conversion with validation
                            date_str = value.decode().strip()
                            if date_str:
                                result[key] = datetime.fromisoformat(date_str)
                            else:
                                result[key] = default
                        else:
                            # Handle string and other types
                            decoded = value.decode().strip()
                            result[key] = decoded if decoded else default
                    except (ValueError, TypeError) as ex:
                        logger.debug(f"Error converting value for key {key}: {ex}")
                        result[key] = default
                else:
                    result[key] = default

            return result
        except Exception as ex:
            logger.error(f"Error parsing Redis hash: {ex}")
            return defaults

    async def get_user_data_by_ip(self, ip_address: str) -> UserData:
        """Get user data by IP with batch processing"""
        try:
            return await self.batch_processor.add_to_batch(
                "get_user_data_by_ip",
                (ip_address,),
                priority=BatchPriority.HIGH
            )
        except Exception as ex:
            logger.error(f"Error fetching user data by IP: {str(ex)}")
            return self.create_default_user_data(ip_address)

    async def increment_usage(self, user_id: Optional[int], ip_address: str) -> UserData:
        """Increment usage count with batch processing"""
        try:
            return await self.batch_processor.add_to_batch(
                "increment_usage",
                (user_id, str(ip_address)),
                priority=BatchPriority.URGENT
            )
        except Exception as ex:
            logger.error(f"Error in increment_usage: {str(ex)}")
            return self.create_default_user_data(ip_address)

    async def check_rate_limit(self, key: str) -> bool:
        """Check rate limit with batch processing"""
        try:
            return await self.batch_processor.add_to_batch(
                "check_rate_limit",
                (key,),
                priority=BatchPriority.URGENT
            )
        except Exception as ex:
            logger.error(f"Error in check_rate_limit: {str(ex)}")
            return False

    async def get_all_user_keys(self) -> List[str]:
        """Get all user and IP-based keys"""
        try:
            async with self.get_pipeline() as pipe:
                pipe.keys("user_data:*")
                pipe.keys("ip:*")
                user_keys, ip_keys = await pipe.execute()
                return user_keys + ip_keys
        except Exception as ex:
            logger.error(f"Error getting all user keys: {str(ex)}")
            return []

    async def reset_daily_usage(self):
        """Reset daily usage counts for all users"""
        try:
            keys = await self.get_all_user_keys()
            tasks = []
            for key in keys:
                task = self.batch_processor.add_to_batch(
                    "reset_daily_usage",
                    (key,),
                    priority=BatchPriority.LOW
                )
                tasks.append(task)
            await self._gather_with_cleanup(tasks)
        except Exception as ex:
            logger.error(f"Error resetting daily usage: {str(ex)}")

    async def sync_to_database(self, db: AsyncSession):
        """Synchronize Redis data to database with hash structure"""
        try:
            all_user_data = await self.redis.eval(GET_ALL_USER_DATA_SCRIPT, [], [])

            async with db.begin():
                for data in all_user_data:
                    try:
                        key_type, key_id = data[0].decode(), data[1].decode()
                        user_data_dict = {}

                        # Convert field-value pairs to dict
                        for field_data in data[2:]:
                            field = field_data[0].decode()
                            value = field_data[1].decode()

                            # Convert numeric fields
                            if field in ["requests_today", "remaining_requests", "id"]:
                                value = int(value)
                            # Convert datetime fields
                            elif field in ["last_request", "last_reset"]:
                                value = datetime.fromisoformat(value)

                            user_data_dict[field] = value

                        # Create Usage record
                        usage = Usage(
                            user_id=user_data_dict.get("id", -1),
                            ip_address=user_data_dict.get("ip_address"),
                            requests_today=user_data_dict.get("requests_today", 0),
                            last_reset=user_data_dict.get("last_reset"),
                            last_request=user_data_dict.get("last_request"),
                            tier=user_data_dict.get("tier", "unauthenticated")
                        )
                        db.add(usage)
                    except Exception as ex:
                        logger.error(f"Error processing user data record: {ex}")
                        continue

                await db.commit()
            logger.info("Redis data synced to database successfully")
        except Exception as ex:
            logger.error(f"Error syncing Redis data to database: {str(ex)}")
            raise

    async def sync_all_username_mappings(self, db: AsyncSession):
        """Synchronize username mappings from database to Redis using hashes"""
        try:
            async with db.begin():
                result = await db.execute(select(User))
                users = result.scalars().all()
                current_time = datetime.now(pytz.utc)

                async with self.get_pipeline() as pipe:
                    for user in users:
                        key = self._get_key(user.id, user.ip_address)
                        # Create complete hash for each user
                        mapping = {
                            "id": str(user.id),
                            "username": user.username,
                            "ip_address": user.ip_address,
                            "tier": user.tier,
                            "requests_today": "0",
                            "remaining_requests": str(settings.RateLimit.get_limit(user.tier)),
                            "last_request": current_time.isoformat(),
                            "last_reset": current_time.isoformat()
                        }
                        pipe.hset(key, mapping=mapping)
                        pipe.expire(key, 86400)

                    await pipe.execute()

            logger.info("Username mappings synced successfully")
        except Exception as ex:
            logger.error(f"Error syncing username mappings: {str(ex)}")
            raise

    async def token_management(self, user_id: int, operation: str, token: Optional[str] = None, expire_time: int = 3600) -> Any:
        """Unified token management method using hash fields"""
        key = f"user_data:{user_id}"
        try:
            async with self.get_pipeline() as pipe:
                if operation == "add":
                    pipe.hset(key, "active_token", token)
                    pipe.expire(key, expire_time)
                    results = await pipe.execute()
                    return bool(results[0])
                elif operation == "remove":
                    return bool(await self.redis.hdel(key, "active_token"))
                elif operation == "get":
                    result = await self.redis.hget(key, "active_token")
                    return result.decode() if result else None
                elif operation == "check":
                    stored_token = await self.redis.hget(key, "active_token")
                    return stored_token == token.encode() if stored_token else False
        except Exception as ex:
            logger.error(f"Error in token management ({operation}): {str(ex)}")
            return None if operation == "get" else False

    async def add_active_token(self, user_id: int, token: str, expire_time: int = 3600):
        return await self.token_management(user_id, "add", token, expire_time)

    async def remove_active_token(self, user_id: int):
        return await self.token_management(user_id, "remove")

    async def get_active_token(self, user_id: int) -> Optional[str]:
        return await self.token_management(user_id, "get")

    async def is_token_active(self, user_id: int, token: str) -> bool:
        return await self.token_management(user_id, "check", token)

    async def set_username_to_id_mapping(self, username: str, user_id: int) -> bool:
        """Set username to ID mapping with batch processing"""
        try:
            return await self.batch_processor.add_to_batch(
                "set_username_mapping",
                (username, user_id),
                priority=BatchPriority.LOW
            )
        except Exception as ex:
            logger.error(f"Error setting username to ID mapping: {str(ex)}")
            return False

    async def check_redis(self) -> str:
        """Check Redis connection health"""
        try:
            async with self.get_connection():
                await self.redis.ping()
                return "ok"
        except Exception as ex:
            logger.error(f"Redis health check failed: {str(ex)}")
            return "error"

    async def get_connection_stats(self) -> RedisConnectionStats:
        """Get Redis connection statistics"""
        try:
            async with self.get_connection():
                info = await self.redis.info("clients")
                return RedisConnectionStats(
                    connected_clients=info["connected_clients"],
                    blocked_clients=info["blocked_clients"],
                    tracking_clients=info.get("tracking_clients", 0)
                )
        except Exception as ex:
            logger.error(f"Error getting connection stats: {str(ex)}")
            return RedisConnectionStats(
                connected_clients=0,
                blocked_clients=0,
                tracking_clients=0
            )

    def create_default_user_data(self, ip_address: str = "unknown") -> UserData:
        """Create default user data object with all required fields"""
        current_time = datetime.now(pytz.utc)
        return UserData(
            id=-1,
            username=f"ip:{ip_address}",
            ip_address=ip_address,
            tier="unauthenticated",
            remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
            requests_today=0,
            last_request=current_time,
            last_reset=current_time
        )

    async def _gather_with_cleanup(self, tasks: List[asyncio.Task]) -> List[Any]:
        """Gather tasks with proper cleanup"""
        try:
            return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise
        finally:
            for task in tasks:
                try:
                    if not task.done():
                        task.cancel()
                    await task
                except Exception:
                    pass

    # async def clean_expired_tokens(self):
    #     try:
    #         all_user_keys = await self.redis.keys("user:*:active_tokens")
    #         for key in all_user_keys:
    #             active_tokens = await self.redis.smembers(key)
    #             for token in active tokens:
    #                 # Check if token is expired (you may need to decode and check the expiration)
    #                 # For simplicity, let's assume tokens older than 24 hours are expired. Need to change this later.
    #                 token_added_time = await self.redis.zscore(f"{key}:timestamps", token)
    #                 if token_added_time and datetime.now().timestamp() - token_added_time > 86400:
    #                     await self.redis.srem(key, token)
    #                     await self.redis.zrem(f"{key}:timestamps", token)
    #     except Exception as ex:
    #         logger.error(f"Error cleaning expired tokens: {str(ex)}")
