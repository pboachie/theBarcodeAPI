import traceback
from redis.asyncio import Redis
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging
import pytz
import asyncio
import ipaddress
import gc
import time
from json import JSONDecodeError
import json

from app.config import settings
from app.utils import IDGenerator
from app.schemas import BatchPriority, UserData, RedisConnectionStats
from app.models import User, Usage
from app.batch_processor import MultiLevelBatchProcessor
from .lua_scripts import INCREMENT_USAGE_SCRIPT, GET_ALL_USER_DATA_SCRIPT

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.increment_usage_sha = None
        self.ip_cache = {}
        # Initialize batch processor
        self.batch_processor = MultiLevelBatchProcessor(self)
        logger.info("Redis manager initialized")


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
        try:
            await self.cleanup_redis_keys()
            await self.load_lua_scripts()
            # Make sure batch processor is started
            if self.batch_processor:
                await self.batch_processor.start()
                logger.info("Batch processor started successfully")
            logger.info("Redis manager started successfully")
        except Exception as e:
            logger.error(f"Error starting Redis manager: {e}")
            raise

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

            logger.debug(f"Opearation starting for {operation} with {len(items)} items")

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
        """Process batch of set_user_data operations"""
        try:
            for (item,), batch_id in items:
                user_data = item['user_data'] if isinstance(item, dict) else item
                if not isinstance(user_data, UserData):
                    continue

                key = f"user_data:{user_data.id}"
                mapping = {
                    "id": str(user_data.id),
                    "username": str(user_data.username),
                    "ip_address": str(user_data.ip_address) if user_data.ip_address else "",
                    "tier": str(user_data.tier),
                    "requests_today": str(user_data.requests_today),
                    "remaining_requests": str(user_data.remaining_requests),
                    "last_request": user_data.last_request.isoformat() if user_data.last_request else datetime.now(pytz.utc).isoformat(),
                    "last_reset": user_data.last_reset.isoformat() if user_data.last_reset else datetime.now(pytz.utc).isoformat()
                }

                pipe.hset(key, mapping=mapping)
                pipe.expire(key, 86400)

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(bool(results[i * 2]))

        except Exception as ex:
            logger.error(f"Error in _process_set_user_data: {ex}", exc_info=True)
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)

    async def _process_get_user_data(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of get_user_data operations"""
        try:
            # Prepare all Redis commands
            for (item,), batch_id in items:
                user_id = item['user_id'] if isinstance(item, dict) else item
                key = f"user_data:{user_id}"
                pipe.hgetall(key)

            # Execute all commands
            results = await pipe.execute()

            # Process results
            for i, ((item,), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if not future or future.done():
                    continue

                try:
                    if results[i]:
                        # Convert Redis result to UserData
                        user_data_dict = {}
                        for k, v in results[i].items():
                            key_str = k.decode() if isinstance(k, bytes) else str(k)
                            val_str = v.decode() if isinstance(v, bytes) else str(v)
                            user_data_dict[key_str] = val_str

                        # Convert numeric fields
                        for field in ['requests_today', 'remaining_requests']:
                            if field in user_data_dict:
                                user_data_dict[field] = int(user_data_dict[field])

                        # Convert datetime fields
                        current_time = datetime.now(pytz.utc)
                        for field in ['last_request', 'last_reset']:
                            if field in user_data_dict and user_data_dict[field]:
                                try:
                                    user_data_dict[field] = datetime.fromisoformat(user_data_dict[field])
                                except ValueError:
                                    user_data_dict[field] = current_time

                        # Ensure required fields
                        user_data_dict.setdefault('id', str(item['user_id'] if isinstance(item, dict) else item))
                        user_data_dict.setdefault('username', f"user_{user_data_dict['id']}")
                        user_data_dict.setdefault('tier', 'unauthenticated')

                        user_data = UserData(**user_data_dict)
                        future.set_result(user_data)
                    else:
                        future.set_result(None)
                except Exception as ex:
                    logger.error(f"Error processing user data: {ex}", exc_info=True)
                    future.set_result(None)

        except Exception as ex:
            logger.error(f"Error in _process_get_user_data: {ex}", exc_info=True)
            for _, batch_id in items:
                self._cleanup_future(batch_id, None)

    async def _process_increment_usage(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of increment usage operations"""
        try:
            current_time = datetime.now(pytz.utc).isoformat()
            operation_futures = []

            for (user_id, ip_address), batch_id in items:
                key = self._get_key(user_id, ip_address)
                pipe.evalsha(
                    self.increment_usage_sha,
                    1,
                    key,
                    str(user_id if user_id else -1),
                    str(ip_address),
                    str(settings.RateLimit.get_limit("unauthenticated")),
                    current_time
                )
                operation_futures.append((key, ip_address, batch_id))

            results = await pipe.execute()

            for i, (key, ip_address, batch_id) in enumerate(operation_futures):
                lua_result = results[i]
                future = pending_results.get(batch_id)

                if future and not future.done():
                    try:
                        if lua_result:
                            # Convert Lua result list to dict
                            result_dict = {}
                            for j in range(0, len(lua_result), 2):
                                k = lua_result[j].decode() if isinstance(lua_result[j], bytes) else str(lua_result[j])
                                v = lua_result[j+1].decode() if isinstance(lua_result[j+1], bytes) else str(lua_result[j+1])
                                result_dict[k] = v

                            # Create user data from result (Throw exception if missing fields)
                            required_fields = ["id", "ip_address", "username", "tier", "requests_today", "remaining_requests", "last_request", "last_reset"]
                            for field in required_fields:
                                if field not in result_dict or result_dict[field] is None:
                                    raise ValueError(f"Missing required field: {field}")

                            user_data_dict = {
                                "id": str(result_dict.get("id")),
                                "ip_address": result_dict.get("ip_address"),
                                "username": result_dict.get("username"),
                                "tier": result_dict.get("tier"),
                                "requests_today": int(result_dict.get("requests_today")),
                                "remaining_requests": int(result_dict.get("remaining_requests")),
                                "last_request": datetime.fromisoformat(result_dict.get("last_request")),
                                "last_reset": datetime.fromisoformat(result_dict.get("last_reset"))
                            }

                            user_data = UserData(**user_data_dict)
                            future.set_result(user_data)
                        else:
                            logger.error(f"No result from Lua script for {key}")
                            future.set_result(self.create_default_user_data(ip_address))
                    except Exception as ex:
                        logger.error(f"Error processing increment result: {ex}")
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
                key = f"ip:{ip_address}"
                pipe.hgetall(key)

            results = await pipe.execute()

            for i, ((ip_address,), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    if results[i]:
                        try:
                            defaults = self.create_default_user_data(ip_address)
                            user_data_dict = self._parse_redis_hash(results[i], defaults)
                            future.set_result(UserData(**user_data_dict))
                        except Exception as ex:
                            logger.error(f"Error processing user data: {ex}")
                            future.set_result(await self.create_default_user_data(ip_address))
                    else:
                        future.set_result(await self.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error in _process_get_user_data_by_ip: {ex}")
            for (ip_address,), batch_id in items:
                future = pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(await self.create_default_user_data(ip_address))

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
        """Process batch of get_user_data operations"""
        try:
            for (user_id,), batch_id in items:
                key = f"user_data:{user_id}"
                pipe.hgetall(key)

            results = await pipe.execute()

            for i, ((user_id,), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    try:
                        if results[i]:
                            # Convert Redis hash to UserData
                            data = results[i]
                            user_data_dict = {}

                            for k, v in data.items():
                                key_str = k.decode() if isinstance(k, bytes) else str(k)
                                val_str = v.decode() if isinstance(v, bytes) else str(v)
                                user_data_dict[key_str] = val_str

                            # Convert types as needed
                            for field in ['requests_today', 'remaining_requests']:
                                if field in user_data_dict:
                                    user_data_dict[field] = int(user_data_dict[field])

                            for field in ['last_request', 'last_reset']:
                                if field in user_data_dict:
                                    try:
                                        user_data_dict[field] = datetime.fromisoformat(user_data_dict[field])
                                    except (ValueError, TypeError):
                                        user_data_dict[field] = datetime.now(pytz.utc)

                            # Ensure all required fields
                            if 'id' not in user_data_dict:
                                user_data_dict['id'] = str(user_id)
                            if 'tier' not in user_data_dict:
                                user_data_dict['tier'] = 'unauthenticated'

                            user_data = UserData(**user_data_dict)
                            future.set_result(user_data)
                        else:
                            future.set_result(None)
                    except Exception as ex:
                        logger.error(f"Error processing user data result: {ex}", exc_info=True)
                        future.set_result(None)

        except Exception as ex:
            logger.error(f"Error in batch get_user_data: {str(ex)}", exc_info=True)
            for _, batch_id in items:
                if batch_id in self.pending_results:
                    future = self.pending_results[batch_id]
                    if not future.done():
                        future.set_result(None)

    async def _batch_set_user_data(self, items: List[Tuple[UserData, str]], pipe):
        """Process batch of set user data operations"""
        try:
            for (user_data,), batch_id in items:
                key = f"user_data:{user_data.id}"
                current_time = datetime.now(pytz.utc)

                mapping = {
                    "id": str(user_data.id),
                    "username": str(user_data.username or f"ip:{user_data.ip_address}"),
                    "ip_address": str(user_data.ip_address),
                    "tier": str(user_data.tier or "unauthenticated"),
                    "requests_today": str(user_data.requests_today or 0),
                    "remaining_requests": str(user_data.remaining_requests or
                        settings.RateLimit.get_limit("unauthenticated")),
                    "last_request": user_data.last_request.isoformat() if user_data.last_request
                        else current_time.isoformat(),
                    "last_reset": user_data.last_reset.isoformat() if user_data.last_reset
                        else current_time.isoformat()
                }

                await pipe.hset(key, mapping=mapping)
                await pipe.expire(key, 86400)  # 24 hour expiry

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                self._cleanup_future(batch_id, bool(results[i * 2]))

        except Exception as ex:
            logger.error(f"Error in batch set_user_data: {ex}", exc_info=True)
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

                            required_fields = ["id", "ip_address", "username", "tier", "requests_today", "remaining_requests", "last_request", "last_reset"]
                            for field in required_fields:
                                if field.encode() not in data:
                                    raise ValueError(f"Missing required field: {field}")

                            user_data_dict = {
                                "id": str(data[b"id"].decode()),
                                "ip_address": data[b"ip_address"].decode(),
                                "username": data[b"username"].decode(),
                                "tier": data[b"tier"].decode(),
                                "requests_today": int(data[b"requests_today"].decode()),
                                "remaining_requests": int(data[b"remaining_requests"].decode()),
                                "last_request": datetime.fromisoformat(data[b"last_request"].decode()),
                                "last_reset": datetime.fromisoformat(data[b"last_reset"].decode())
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
                        required_fields = ["ip_address", "requests_today", "remaining_requests", "last_request"]
                        for field in required_fields:
                            if field.encode() not in results[i]:
                                raise ValueError(f"Missing required field: {field}")

                        user_data_dict = {
                            "ip_address": ip_address,
                            "requests_today": int(results[i][b"requests_today"].decode()),
                            "remaining_requests": int(results[i][b"remaining_requests"].decode()),
                            "last_request": datetime.fromisoformat(results[i][b"last_request"].decode())
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
            self.batch_processor._handle_batch_error(current_batch)
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

    def _get_key(self, user_id: Optional[str] = None, ip_address: Optional[str] = None) -> str:
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
        """Set user data in Redis using consistent hash storage"""
        try:
            # Create user data key and IP key
            user_key = f"user_data:{user_data.id}"
            ip_key = f"ip:{user_data.ip_address}"

            # Prepare mapping data
            mapping = {
                "id": str(user_data.id),
                "username": str(user_data.username),
                "ip_address": str(user_data.ip_address),
                "tier": str(user_data.tier),
                "requests_today": str(user_data.requests_today),
                "remaining_requests": str(user_data.remaining_requests),
                "last_request": user_data.last_request.isoformat(),
                "last_reset": user_data.last_reset.isoformat()
            }

            # Store both user data and IP mapping as hashes
            async with self.redis.pipeline() as pipe:
                # Store main user data
                await pipe.hset(user_key, mapping=mapping)
                await pipe.expire(user_key, 86400)  # 24 hour expiry

                # Store IP mapping as a hash with minimal data
                ip_mapping = {
                    "id": str(user_data.id),
                    "ip_address": str(user_data.ip_address)
                }
                await pipe.hset(ip_key, mapping=ip_mapping)
                await pipe.expire(ip_key, 86400)  # 24 hour expiry

                await pipe.execute()

            logger.debug(f"Successfully set user data for {user_key}")
            return True

        except Exception as e:
            logger.error(f"Error in set_user_data: {str(e)}", exc_info=True)
            return False

    async def get_user_data(self, user_id: Optional[str], ip_address: str) -> UserData:
        """Get user data from Redis with fallback to default"""
        try:
            key = self._get_key(user_id, ip_address)
            async with self.get_connection():
                data = await self.redis.hgetall(key)
                if data:
                    try:
                        defaults = self.create_default_user_data(ip_address)

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

    def _decode_redis_hash(self, hash_data: Dict[bytes, bytes], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decode Redis hash data with proper type conversion.

        Args:
            hash_data: Raw Redis hash data with byte keys and values
            defaults: Dictionary of default values with their expected types

        Returns:
            Dict with properly decoded and typed values
        """
        result = {}
        try:
            # First decode all bytes to strings
            str_data = {
                k.decode('utf-8') if isinstance(k, bytes) else k:
                v.decode('utf-8') if isinstance(v, bytes) else v
                for k, v in hash_data.items()
            }

            logger.debug(f"Decoded Redis hash data: {str_data}")

            # Convert values based on default types
            for key, default in defaults.items():
                if key in str_data:
                    value = str_data[key].strip()
                    try:
                        if isinstance(default, int):
                            result[key] = int(value) if value else default
                        elif isinstance(default, datetime):
                            result[key] = datetime.fromisoformat(value) if value else default
                        else:
                            result[key] = value if value else default
                    except (ValueError, TypeError) as ex:
                        logger.error(f"Error converting {key}={value}: {ex}")
                        result[key] = default
                else:
                    result[key] = default

            return result

        except Exception as ex:
            logger.error(f"Error decoding Redis hash: {ex}")
            return defaults


    def _parse_redis_hash(self, data: Dict[bytes, bytes], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Redis hash data with proper type conversion"""
        result = {}
        try:
            # Convert byte keys and values to strings
            str_data = {
                k.decode('utf-8') if isinstance(k, bytes) else k:
                v.decode('utf-8') if isinstance(v, bytes) else v
                for k, v in data.items()
            }

            # Use provided defaults for all fields
            result = defaults.copy()

            # Update with actual values from Redis
            for key, value in str_data.items():
                if key in result:
                    try:
                        if isinstance(result[key], int):
                            result[key] = int(value)
                        elif isinstance(result[key], datetime):
                            result[key] = datetime.fromisoformat(value)
                        else:
                            result[key] = value
                    except (ValueError, TypeError) as ex:
                        logger.error(f"Error converting {key}={value}: {ex}")

            return result
        except Exception as ex:
            logger.error(f"Error parsing Redis hash: {ex}")
            return defaults

    async def get_user_data_by_ip(self, ip_address: str) -> Optional[UserData]:
        """Get user data by IP address, using consistent hash storage"""
        try:
            # Always use hash storage for IP keys
            ip_key = f"ip:{ip_address}"
            ip_data = await self.redis.hgetall(ip_key)

            if ip_data:
                # If we have IP data, check for user_id mapping
                user_id = None
                if b'id' in ip_data:
                    user_id = ip_data[b'id'].decode()
                elif 'id' in ip_data:
                    user_id = ip_data['id']

                if user_id:
                    # Get full user data if we have an ID
                    user_key = f"user_data:{user_id}"
                    data = await self.redis.hgetall(user_key)
                    if not data:  # If no user data found, fall back to IP data
                        data = ip_data
                else:
                    data = ip_data
            else:
                return None

            if data:
                try:
                    # Convert all values to strings if they're bytes
                    user_data_dict = {}
                    for k, v in data.items():
                        key_str = k.decode() if isinstance(k, bytes) else str(k)
                        value_str = v.decode() if isinstance(v, bytes) else str(v)
                        user_data_dict[key_str] = value_str

                    # Ensure all required fields are present with defaults
                    now = datetime.now(pytz.utc)
                    default_values = {
                        'id': user_data_dict.get('id') or IDGenerator.generate_id(),
                        'username': user_data_dict.get('username') or f'ip:{ip_address}',
                        'ip_address': ip_address,
                        'tier': user_data_dict.get('tier') or 'unauthenticated',
                        'requests_today': int(user_data_dict.get('requests_today', 0)),
                        'remaining_requests': int(user_data_dict.get('remaining_requests',
                            settings.RateLimit.get_limit("unauthenticated"))),
                        'last_request': datetime.fromisoformat(user_data_dict.get('last_request',
                            now.isoformat())),
                        'last_reset': datetime.fromisoformat(user_data_dict.get('last_reset',
                            now.isoformat()))
                    }

                    return UserData(**default_values)

                except Exception as ex:
                    logger.error(f"Error parsing user data: {ex}", exc_info=True)
                    return None
            return None
        except Exception as ex:
            logger.error(f"Error fetching user data by IP: {str(ex)}", exc_info=True)
            return None

    async def increment_usage(self, user_id: Optional[str], ip_address: str) -> UserData:
        """Increment usage count with batch processing"""
        try:
            key = self._get_key(user_id, ip_address)
            logger.debug(f"Starting increment_usage for {key}")

            result = await self.batch_processor.add_to_batch(
                "increment_usage",
                (user_id, str(ip_address)),
                priority=BatchPriority.URGENT
            )

            if not isinstance(result, UserData):
                logger.error(f"Invalid result type from increment: {type(result)}")
                return await self.create_default_user_data(ip_address)

            logger.debug(f"Increment completed for {key}: requests={result.requests_today}, remaining={result.remaining_requests}")
            return result

        except Exception as ex:
            logger.error(f"Error in increment_usage: {ex}")
            return await self.create_default_user_data(ip_address)

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

    async def sync_redis_to_db(self, db: AsyncSession):
        """
        Synchronize Redis data to database with proper type handling.

        Args:
            db (AsyncSession): Database session for storing data

        Raises:
            Exception: If synchronization fails
        """
        logger.debug("Starting sync_redis_to_db process.")

        # Field type definitions
        TYPE_MAPPINGS = {
            'integer_fields': {
                'requests_today',
                'remaining_requests'
            },
            'datetime_fields': {
                'last_request',
                'last_reset'
            },
            'required_fields': {
                'id',
                'ip_address',
                'requests_today',
                'last_reset',
                'last_request',
                'tier'
            }
        }

        def convert_value(field: str, value: Any) -> Any:
            """Convert value to appropriate type based on field name"""
            try:
                if field in TYPE_MAPPINGS['integer_fields']:
                    return int(value) if value is not None else 0
                elif field in TYPE_MAPPINGS['datetime_fields']:
                    return datetime.fromisoformat(value) if value else datetime.now(pytz.utc)
                else:
                    return str(value) if value is not None else ""
            except (ValueError, TypeError) as e:
                logger.warning(f"Error converting {field}={value}: {e}")
                if field in TYPE_MAPPINGS['integer_fields']:
                    return 0
                elif field in TYPE_MAPPINGS['datetime_fields']:
                    return datetime.now(pytz.utc)
                return ""

        def create_usage_record(data: dict) -> Usage:
            """Create Usage record with proper defaults"""
            current_time = datetime.now(pytz.utc)
            return Usage(
                user_id=data.get("id"),
                ip_address=data.get("ip_address"),
                requests_today=data.get("requests_today", 0),
                last_reset=data.get("last_reset", current_time),
                last_request=data.get("last_request", current_time),
                tier=data.get("tier", "unauthenticated")
            )

        try:
            logger.debug("Retrieving all user data from Redis.")
            all_user_data = await self.redis.eval(GET_ALL_USER_DATA_SCRIPT, 0)
            logger.debug(f"Retrieved {len(all_user_data)} user data records from Redis.")

            # Process records in batches for better performance
            BATCH_SIZE = 100
            async with db.begin():
                for batch_start in range(0, len(all_user_data), BATCH_SIZE):
                    batch = all_user_data[batch_start:batch_start + BATCH_SIZE]
                    logger.debug(f"Processing batch {batch_start // BATCH_SIZE + 1} with {len(batch)} records.")

                    for index, data in enumerate(batch, start=batch_start):
                        try:
                            key_type, key_id = data[0], data[1]
                            logger.debug(f"Processing record {index + 1}: key_type={key_type}, key_id={key_id}")

                            # Process field-value pairs
                            user_data_dict = {}
                            for field_data in data[2:]:
                                field, value = field_data
                                logger.debug(f"Field: {field}, Value: {value}")
                                user_data_dict[field] = convert_value(field, value)

                            # Validate required fields
                            missing_fields = TYPE_MAPPINGS['required_fields'] - user_data_dict.keys()
                            if missing_fields:
                                logger.warning(f"Missing required fields for record {index + 1}: {missing_fields}")
                                continue

                            # Create and add Usage record
                            usage = create_usage_record(user_data_dict)
                            db.add(usage)
                            logger.debug(f"Added Usage record for user_id={usage.user_id}")

                        except Exception as ex:
                            logger.error(f"Error processing record {index + 1}: {ex}", exc_info=True)
                            continue

                    # Commit each batch
                    try:
                        await db.commit()
                        logger.debug(f"Committed batch {batch_start//BATCH_SIZE + 1}")
                    except Exception as ex:
                        logger.error(f"Error committing batch: {ex}", exc_info=True)
                        await db.rollback()
                        continue

            logger.info("Redis data synced to database successfully")

        except Exception as ex:
            logger.error(f"Error syncing Redis data to database: {str(ex)}", exc_info=True)
            raise

    async def sync_all_username_mappings(self, db: AsyncSession):
        """Synchronize all username mappings into Redis"""
        try:
            logger.debug("Starting sync_all_username_mappings")
            async with db as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
                logger.debug(f"Retrieved {len(users)} users from the database.")

            async with self.get_pipeline() as pipe:
                for user in users:
                    key = f"username:{user.username or ''}"
                    mapping = {}

                    if user.id is not None:
                        mapping["id"] = str(user.id)
                    if user.username:
                        mapping["username"] = user.username
                    if user.tier:
                        mapping["tier"] = user.tier
                    # if user.api_key:
                    #     mapping["api_key"] = user.api_key

                    if mapping:
                        logger.debug(f"Syncing user: {user.username} with ID: {user.id}")
                        await pipe.hmset(key, mapping)
                    else:
                        logger.warning(f"No valid data to sync for user with ID {user.id}")
                await pipe.execute()
            logger.info("Username mappings synchronized successfully")
        except Exception as ex:
            logger.error(f"Error syncing username mappings: {ex}")
            raise

    async def sync_db_to_redis(self, db: AsyncSession):
        """Synchronize database data to Redis with hash structure"""
        logger.debug("Starting sync_db_to_redis process.")
        try:
            async with db as session:
                result = await session.execute(select(Usage))
                usages = result.scalars().all()

            async with self.get_pipeline() as pipe:
                for usage in usages:
                    key = self._get_key(usage.user_id, usage.ip_address)
                    mapping = {
                        "id": str(usage.user_id),
                        "user_identifier": usage.user_identifier,
                        "ip_address": usage.ip_address,
                        "requests_today": str(usage.requests_today),
                        "remaining_requests": str(usage.remaining_requests),
                        "last_request": usage.last_request.isoformat(),
                        "last_reset": usage.last_reset.isoformat(),
                        "tier": usage.tier
                    }
                    await pipe.hmset(key, mapping)
                await pipe.execute()
            logger.info("Database data synced to Redis successfully.")
        except Exception as ex:
            logger.error(f"Error syncing database data to Redis: {str(ex)}", exc_info=True)
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

    async def create_default_user_data(self, ip_address: str) -> UserData:
        """Create default user data"""
        try:
            # First check if we already have data for this IP
            existing_data = await self.get_user_data_by_ip(ip_address)
            if existing_data:
                return existing_data

            # If no existing data, create new
            current_time = datetime.now(pytz.utc)
            user_data = UserData(
                id=IDGenerator.generate_id(),
                username=f"ip:{ip_address}",
                ip_address=ip_address,
                tier="unauthenticated",
                remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
                requests_today=0,
                last_request=current_time,
                last_reset=current_time
            )

            # Store user data
            if await self.set_user_data(user_data):
                return user_data
            else:
                raise Exception("Failed to store user data")

        except Exception as ex:
            logger.error(f"Error creating default user data: {ex}", exc_info=True)
            raise

    async def cleanup_redis_keys(self):
        """Clean up any inconsistent Redis keys"""
        try:
            # Get all IP and user data keys
            ip_keys = await self.redis.keys("ip:*")
            user_keys = await self.redis.keys("user_data:*")

            async with self.redis.pipeline() as pipe:
                # Check each IP key
                for key in ip_keys:
                    key_type = await self.redis.type(key)
                    if key_type != b'hash':
                        # If not a hash, delete it
                        await pipe.delete(key)

                # Check each user data key
                for key in user_keys:
                    key_type = await self.redis.type(key)
                    if key_type != b'hash':
                        # If not a hash, delete it
                        await pipe.delete(key)

                await pipe.execute()

            logger.info("Completed Redis key cleanup")
        except Exception as ex:
            logger.error(f"Error during Redis cleanup: {str(ex)}", exc_info=True)

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

    async def get_metrics(self) -> dict:
        """Get batch processing metrics and Redis stats"""
        try:
            # Get Redis info
            info = await self.redis.info()
            pool = self.redis.connection_pool

            # Get batch processor stats
            batch_metrics = {
                priority.name: {
                    "queue_size": len(processor.batch),
                    "processing": processor.processing,
                    "interval_ms": int(processor.interval * 1000)
                }
                for priority, processor in self.batch_processor.processors.items()
            }

            return {
                "redis": {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "0"),
                    "total_connections_received": info.get("total_connections_received", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                },
                "connection_pool": {
                    "max_connections": pool.max_connections,
                    "in_use_connections": len(pool._in_use_connections),
                    "available_connections": len(pool._available_connections)
                },
                "batch_processors": batch_metrics
            }
        except Exception as ex:
            logger.error(f"Error getting metrics: {ex}")
            return {
                "error": str(ex),
                "redis": {},
                "connection_pool": {},
                "batch_processors": {}
            }

    async def get_user_data_by_username(self, username: str) -> Optional[UserData]:
        """Retrieve user data by username using batch processor"""
        try:
            # Add request to batch processor with high priority
            batch_response = await self.batch_processor.add_to_batch(
                "get_user_data",
                username,
                priority=BatchPriority.HIGH
            )

            if not batch_response:
                logger.warning(f"No data found for username: {username}")
                return None

            try:
                # If response is already a UserData object
                if isinstance(batch_response, UserData):
                    return batch_response

                # Convert Redis hash to UserData object
                if isinstance(batch_response, dict):
                    required_fields = ["id", "username", "ip_address", "tier", "requests_today", "remaining_requests", "last_request", "last_reset"]
                    for field in required_fields:
                        if field not in batch_response:
                            raise ValueError(f"Missing required field: {field}")

                    user_data_dict = {
                        "id": str(batch_response["id"]),
                        "username": batch_response["username"],
                        "ip_address": batch_response["ip_address"],
                        "tier": batch_response["tier"],
                        "requests_today": int(batch_response["requests_today"]),
                        "remaining_requests": int(batch_response["remaining_requests"]),
                        "last_request": datetime.fromisoformat(batch_response["last_request"]),
                        "last_reset": datetime.fromisoformat(batch_response["last_reset"])
                    }
                    return UserData(**user_data_dict)

                logger.error(f"Unexpected response type for username {username}: {type(batch_response)}")
                return None
            except Exception as ex:
                logger.error(f"Error retrieving user data for username {username}: {str(ex)}")
                return None
        except Exception as ex:
            logger.error(f"Error getting user data by username: {str(ex)}")
            return None
        finally:
            self.batch_processor._cleanup_pending_results()