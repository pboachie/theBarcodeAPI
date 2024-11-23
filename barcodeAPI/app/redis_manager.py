import traceback
from redis.asyncio import Redis
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from sqlalchemy import or_
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
from .lua_scripts import INCREMENT_USAGE_SCRIPT, GET_ALL_USER_DATA_SCRIPT, RATE_LIMIT_SCRIPT

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.increment_usage_sha = None
        self.pending_results = {}
        self.rate_limit_sha = None
        self.ip_cache = {}
        self.current_batch_id = 0

        # Initialize batch processor
        self.batch_processor = MultiLevelBatchProcessor(self)
        self._batch_lock = asyncio.Lock()
        logger.info("Redis manager initialized")


    @asynccontextmanager
    async def get_connection(self):
        """Context manager to handle Redis connections with proper cleanup"""
        conn = await self.redis.connection_pool.get_connection("_") # type: ignore

        if not conn:
            raise ConnectionError("Failed to get Redis connection from pool")

        try:
            yield conn
        finally:
            await conn.disconnect()
            self.redis.connection_pool._available_connections.append(conn)

    @asynccontextmanager
    async def get_pipeline(self):
        """Context manager for Redis pipeline operations"""
        pipe = self.redis.pipeline()
        try:
            yield await pipe
        finally:
            await (await pipe).reset()

    async def load_lua_scripts(self):
        """Load Lua scripts into Redis and store their SHAs"""
        try:
            self.increment_usage_sha = await self.redis.script_load(INCREMENT_USAGE_SCRIPT)
            self.rate_limit_sha = await self.redis.script_load(RATE_LIMIT_SCRIPT)
            self.get_all_user_data_sha = await self.redis.script_load(GET_ALL_USER_DATA_SCRIPT)
            logger.info("Lua scripts loaded successfully with SHAs:")
            logger.info(f"INCREMENT_USAGE_SCRIPT SHA: {self.increment_usage_sha}")
            logger.info(f"RATE_LIMIT_SCRIPT SHA: {self.rate_limit_sha}")
            logger.info(f"GET_ALL_USER_DATA_SCRIPT SHA: {self.get_all_user_data_sha}")
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
            self.redis.connection_pool.disconnect()
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
                results = await pipe.execute()

                # Process results if necessary
                if len(results) != len(items) * 2:
                    logger.error(f"Unexpected number of results from pipeline: expected {len(items) * 2}, got {len(results)}")
                    for _, batch_id in items:
                        future = pending_results.get(batch_id)
                        if future and not future.done():
                            future.set_result(False)
                    return

                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        future.set_result(bool(results[i * 2]))
            else:
                results = await pipe.execute()
            if operation == "get_user_data":
                results = await pipe.execute()
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        future.set_result(results[i])
            elif operation == "get_user_data_by_ip":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        if results[i]:
                            try:
                                defaults = await self.create_default_user_data(items[i][0][0])
                                user_data_dict = self._decode_redis_hash(results[i], defaults.__dict__)
                                future.set_result(UserData(**user_data_dict))
                            except Exception as ex:
                                logger.error(f"Error processing user data: {ex}")
                                future.set_result(await self.create_default_user_data(items[i][0][0]))
                        else:
                            future.set_result(await self.create_default_user_data(items[i][0][0]))
            elif operation == "increment_usage":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        try:
                            if results[i]:
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
                                future.set_result(self.create_default_user_data(items[i][0][1]))
                        except Exception as ex:
                            logger.error(f"Error parsing increment usage result: {ex}")
                            future.set_result(self.create_default_user_data(items[i][0][1]))
            elif operation == "check_rate_limit":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        future.set_result(results[i] != -1)
            elif operation == "is_token_active":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        result = results[i].decode() if results[i] else None
                        future.set_result(result == items[i][0][1])
            elif operation == "get_active_token":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        result = results[i].decode() if results[i] else None
                        future.set_result(result)
            elif operation == "reset_daily_usage":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        future.set_result(True)
            elif operation == "set_username_mapping":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        future.set_result(bool(results[i]))
            elif operation == "get_user_data_by_ip":
                for i, (_, batch_id) in enumerate(items):
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        if results[i]:
                            try:
                                defaults = await self.create_default_user_data(items[i][0][0])
                                user_data_dict = self._decode_redis_hash(results[i], defaults.__dict__)
                                future.set_result(UserData(**user_data_dict))
                            except Exception as ex:
                                logger.error(f"Error processing user data: {ex}")
                                future.set_result(await self.create_default_user_data(items[i][0][0]))
                        else:
                            future.set_result(await self.create_default_user_data(items[i][0][0]))

        except Exception as ex:
            logger.error(f"Error in process_batch_operation {operation}: {ex}", exc_info=True)
            for _, batch_id in items:
                # future = pending_results.get(batch_id)
                # if future and not future.done():
                #     future.set_result(None)
                self._cleanup_future(batch_id, None)

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

            if len(results) != len(items) * 2:
                logger.error(f"Unexpected number of results from pipeline: expected {len(items) * 2}, got {len(results)}")
                for _, batch_id in items:
                    future = pending_results.get(batch_id)
                    if future and not future.done():
                        future.set_result(False)
                return

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
            for (user_id, ip_address), batch_id in items:
                pipe.evalsha(
                    self.increment_usage_sha,
                    1,
                    f"user_data:{user_id}",
                    user_id,
                    ip_address,
                    settings.RateLimit.get_limit("unauthenticated"),
                    datetime.now(pytz.utc).isoformat()
                )
            results = await pipe.execute()

            if len(results) != len(items):
                logger.error(f"Unexpected number of results from pipeline: expected {len(items)}, got {len(results)}")
                # Set default values for missing results
                for (_, batch_id) in items:
                    user_data = await self.get_default_value("increment_usage")
                    self._cleanup_future(batch_id, user_data)
                return

            for result, (_, batch_id) in zip(results, items):
                if result and isinstance(result, dict):
                    user_data = self._decode_redis_hash(
                        result,
                        (await self.get_default_value("increment_usage")).__dict__
                    )
                    self._cleanup_future(batch_id, user_data)
                else:
                    logger.error(f"Invalid result type from increment: {type(result)}")
                    user_data = await self.get_default_value("increment_usage")
                    self._cleanup_future(batch_id, user_data)
        except Exception as ex:
            logger.error(f"Error in _process_increment_usage: {ex}")
            for (_, batch_id) in items:
                user_data = await self.get_default_value("increment_usage")
                self._cleanup_future(batch_id, user_data)

    def _convert_list_to_dict(self, data: List[Any]) -> Dict[bytes, bytes]:
        """Convert list to dict converting strings to bytes"""
        result = {}
        for i in range(0, len(data), 2):
            key = data[i].encode('utf-8') if isinstance(data[i], str) else data[i]
            value = data[i+1].encode('utf-8') if isinstance(data[i+1], str) else data[i+1]
            result[key] = value
        return result

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
            str_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in hash_data.items()}

            logger.debug(f"Decoded Redis hash data: {str_data}")

            # Start with defaults
            result = defaults.copy()

            # Update with actual values from Redis
            for key, value in str_data.items():
                if key in result:
                    value_str = str(value).strip()
                    try:
                        if isinstance(result[key], int):
                            result[key] = int(value_str) if value_str else result[key]
                        elif isinstance(result[key], datetime):
                            result[key] = datetime.fromisoformat(value_str) if value_str else result[key]
                        else:
                            result[key] = value_str if value_str else result[key]
                    except (ValueError, TypeError) as ex:
                        logger.error(f"Error converting {key}={value}: {ex}")

            return result
        except Exception as ex:
            logger.error(f"Error parsing Redis hash: {ex}")
            return defaults

    async def _process_check_rate_limit(self, items: List[Tuple[Any, str]], pipe, pending_results):
        """Process batch of rate limit checks"""
        try:
            window = settings.RATE_LIMIT_WINDOW
            limit = settings.RATE_LIMIT_LIMIT
            current_time = datetime.now(pytz.utc).isoformat()

            for (key,), batch_id in items:
                pipe.eval(RATE_LIMIT_SCRIPT, 1, key, window, limit, current_time)

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
                            defaults = await self.create_default_user_data(ip_address)
                            user_data_dict = self._decode_redis_hash(results[i], defaults.__dict__)
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

    async def get_default_value(self, operation: str, item: Any = None) -> Any:
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
            return await self.create_default_user_data(ip_address)
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
            for item, batch_id in items:
                user_data = item if isinstance(item, UserData) else UserData(**item)
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

                pipe.hset(key, mapping=mapping)
                await pipe.expire(key, 86400)  # 24 hour expiry

            results = await pipe.execute()

            for i, (_, batch_id) in enumerate(items):
                self._cleanup_future(batch_id, bool(results[i * 2]))

        except Exception as ex:
            logger.error(f"Error in batch set_user_data: {ex}", exc_info=True)
            for _, batch_id in items:
                self._cleanup_future(batch_id, False)

    def _cleanup_future(self, batch_id: str, result: Any):
        """Cleanup future by setting result"""
        future = self.pending_results.get(batch_id)
        if future and not future.done():
            future.set_result(result)

    async def _batch_increment_usage(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of increment_usage operations using hash fields"""
        try:
            for (user_id, ip_address), batch_id in items:
                key = self._get_key(user_id, ip_address)
                current_time = datetime.now(pytz.utc).isoformat()

                # Use Lua script for atomic increment
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
                            future.set_result(self.create_default_user_data(ip_address))
                    except Exception as ex:
                        logger.error(f"Error parsing increment usage result: {ex}")
                        future.set_result(self.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error in increment_usage batch: {str(ex)}")
            for (_, ip_address), batch_id in items:
                self._cleanup_future(batch_id, self.create_default_user_data(ip_address))

    async def _batch_check_rate_limit(self, items: List[Tuple[Any, str]], pipe):
        """Process batch of rate limit checks using hash fields"""
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
                key_type = await self.redis.type(key)
                if key_type == b'hash':
                    pipe.hset(key, mapping={
                        "requests_today": 0,
                        "remaining_requests": settings.RateLimit().get_limit("unauthenticated")  # Adjust tier as needed
                    })
                elif key.startswith("ip:"):
                    logger.info(f"Converting key {key} to a hash type")
                    # Retrieve existing value if needed
                    # Delete the existing key
                    await self.redis.delete(key)
                    # Set as hash with default values
                    pipe.hset(key, mapping={
                        "requests_today": 0,
                        "remaining_requests": settings.RateLimit().get_limit("unauthenticated")
                    })
                else:
                    logger.warning(f"Key {key} is not a hash and does not match pattern, deleting key and skipping HSET operation")
                    await self.redis.delete(key)
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
                        self._cleanup_future(batch_id, self.create_default_user_data(ip_address))
                else:
                    self._cleanup_future(batch_id, self.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error in get_user_data_by_ip batch: {str(ex)}")
            for (ip_address,), batch_id in items:
                self._cleanup_future(batch_id, self.create_default_user_data(ip_address))

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
                        self._cleanup_future(batch_id, await self.get_default_value(operation))

        except Exception as ex:
            logger.error(f"Error processing operation {operation}: {str(ex)}")
            for _, batch_id in items:
                self._cleanup_future(batch_id, await self.get_default_value(operation))

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
            async with self.get_pipeline() as pipe:
                for operation, items in operation_groups.items():
                    await self._batch_operation_group(operation, items, pipe)

            process_time = (time.time() - start_time) * 1000
            logger.debug(f"Batch processed in {process_time:.2f}ms")

        except Exception as ex:
            logger.error(f"Error processing batch: {str(ex)}\n{traceback.format_exc()}")
            # self.batch_processor.handle_batch_error(current_batch)
        finally:
            for _, batch_id in current_batch:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(await self.get_default_value(operation))
            self.processing = False
            self.last_batch_time = time.time()

    def _group_operations(self, batch: List[Tuple[str, Tuple[Any, str]]]) -> Dict[str, List[Tuple[Any, str]]]:
        """Group batch operations by their type"""
        operation_groups = {}
        for operation, item in batch:
            if operation not in operation_groups:
                operation_groups[operation] = []
            operation_groups[operation].append(item)
        return operation_groups

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
                self._cleanup_future(batch_id, await self.get_default_value(operation))

    def _get_key(self, user_id: Optional[str] = None, ip_address: Optional[str] = None) -> str:
        """Generate normalized Redis key for user data"""
        if user_id is None or user_id == -1:
            ip_str = self.ip_cache.get(ip_address)
            if ip_str is None:
                try:
                    if ip_address is not None:
                        ip = ipaddress.ip_address(ip_address)
                    else:
                        logger.error("ip_address is None")
                        ip_str = "unknown_ip"
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
            if len(item) > 1:
                return str(item[1])
            elif len(item) == 1:
                return str(item[0])
            else:
                return "unknown"
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
                "last_request": user_data.last_request.isoformat() if user_data.last_request else None,
                "last_reset": user_data.last_reset.isoformat() if user_data.last_reset else None
            }

            # Store both user data and IP mapping as hashes
            async with self.redis.pipeline() as pipe:
                # Store main user data
                pipe.hset(user_key, mapping=mapping)
                await pipe.expire(user_key, 86400)  # 24 hour expiry

                # Store IP mapping as a hash with minimal data
                ip_mapping = {
                    "id": str(user_data.id),
                    "ip_address": str(user_data.ip_address)
                }
                pipe.hset(ip_key, mapping=ip_mapping)
                pipe.expire(ip_key, 86400)  # 24 hour expiry

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
                data = await self.redis.hgetall(key) # type: ignore
                if data:
                    try:
                        defaults = await self.create_default_user_data(ip_address)

                        user_data_dict = {}
                        for key, default in defaults.__dict__.items():
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
                        return await self.create_default_user_data(ip_address)
                return await self.create_default_user_data(ip_address)
        except Exception as ex:
            logger.error(f"Error fetching user data: {str(ex)}")
            return await self.create_default_user_data(ip_address)

    # def _decode_redis_hash(self, hash_data: Dict[bytes, bytes], defaults: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Decode Redis hash data with proper type conversion.

    #     Args:
    #         hash_data: Raw Redis hash data with byte keys and values
    #         defaults: Dictionary of default values with their expected types

    #     Returns:
    #         Dict with properly decoded and typed values
    #     """
    #     result = {}
    #     try:
    #         # First decode all bytes to strings
    #         str_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in hash_data.items()}

    #         logger.debug(f"Decoded Redis hash data: {str_data}")

    #         # Start with defaults
    #         result = defaults.copy()

    #         # Update with actual values from Redis
    #         for key, value in str_data.items():
    #             if key in result:
    #                 value_str = str(value).strip()
    #                 try:
    #                     if isinstance(result[key], int):
    #                         result[key] = int(value_str) if value_str else result[key]
    #                     elif isinstance(result[key], datetime):
    #                         result[key] = datetime.fromisoformat(value_str) if value_str else result[key]
    #                     else:
    #                         result[key] = value_str if value_str else result[key]
    #                 except (ValueError, TypeError) as ex:
    #                     logger.error(f"Error converting {key}={value}: {ex}")
    #             if key in result:
    #                 try:
    #                     if isinstance(result[key], int):
    #                         result[key] = int(value)
    #                     elif isinstance(result[key], datetime):
    #                         result[key] = datetime.fromisoformat(str(value))
    #                     else:
    #                         result[key] = value
    #                 except (ValueError, TypeError) as ex:
    #                     logger.error(f"Error converting {key}={value}: {ex}")

    #         return result
    #     except Exception as ex:
    #         logger.error(f"Error parsing Redis hash: {ex}")
    #         return defaults

    async def get_user_data_by_ip(self, ip_address: str) -> Optional[UserData]:
        """Get user data by IP address, using consistent hash storage"""
        try:
            # Always use hash storage for IP keys
            ip_key = f"ip:{ip_address}"
            ip_data = await self.redis.hgetall(ip_key) # type: ignore

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
                    data = await self.redis.hgetall(user_key) # type: ignore
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

        try:
            logger.debug("Retrieving all user data from Redis.")
            all_user_data = await self.redis.eval(GET_ALL_USER_DATA_SCRIPT, 0) # type: ignore
            logger.debug(f"Retrieved {len(all_user_data)} user data records from Redis.")

            # Prepare data for batch operations
            user_records = {}
            usage_records = {}
            processed_user_ids = set()

            for data in all_user_data:
                try:
                    key_type, key_id = data[0], data[1]
                    if key_type == 'ip':
                        continue

                    user_data_dict = {}
                    for field_data in data[2:]:
                        field, value = field_data
                        user_data_dict[field] = value

                    username = user_data_dict.get('username', f"ip:{user_data_dict.get('ip_address')}")
                    current_time = datetime.now(pytz.utc)
                    data_time = datetime.fromisoformat(user_data_dict.get('last_request', current_time.isoformat()))

                    user_dict = {
                        'id': key_id,
                        'username': username,
                        'tier': user_data_dict.get('tier', 'unauthenticated'),
                        'ip_address': user_data_dict.get('ip_address'),
                        'requests_today': int(user_data_dict.get('requests_today', 0)),
                        'remaining_requests': int(user_data_dict.get('remaining_requests', 5000)),
                        'last_request': data_time,
                        'hashed_password': None
                    }

                    usage_dict = {
                        'user_id': key_id,
                        'ip_address': user_data_dict.get('ip_address'),
                        'requests_today': int(user_data_dict.get('requests_today', 0)),
                        'remaining_requests': int(user_data_dict.get('remaining_requests', 5000)),
                        'last_reset': data_time,
                        'last_request': data_time,
                        'tier': user_data_dict.get('tier', 'unauthenticated')
                    }

                    user_records[key_id] = user_dict
                    usage_records[key_id] = usage_dict
                    processed_user_ids.add(key_id)

                except Exception as ex:
                    logger.error(f"Error processing user record: {ex}")
                    continue

            # Fetch existing users and usages
            existing_users = {}
            existing_usages = {}

            if processed_user_ids:
                user_result = await db.execute(select(User).filter(User.id.in_(processed_user_ids)))
                existing_users_list = user_result.scalars().all()
                existing_users = {user.id: user for user in existing_users_list}

                usage_result = await db.execute(select(Usage).filter(Usage.user_id.in_(processed_user_ids)))
                existing_usages_list = usage_result.scalars().all()
                existing_usages = {usage.user_id: usage for usage in existing_usages_list}

            # Prepare users for bulk upsert
            users_to_update = []
            users_to_create = []
            for user_id, user_data in user_records.items():
                if user_id in existing_users:
                    user = existing_users[user_id]
                    data_time = user_data['last_request']
                    if (user.last_request is None or
                        data_time > user.last_request or
                        user_data['remaining_requests'] > user.remaining_requests):

                        user.username = user_data['username']
                        user.tier = user_data['tier']
                        user.ip_address = user_data['ip_address']
                        current_requests = getattr(user, 'requests_today', 0) or 0
                        current_remaining = getattr(user, 'remaining_requests', 0) or 0
                        setattr(user, 'requests_today', min(int(user_data['requests_today']), int(current_requests)))
                        setattr(user, 'remaining_requests', max(int(user_data['remaining_requests']), int(current_remaining)))
                        setattr(user, 'last_request', data_time)
                        users_to_update.append(user)
                        logger.debug(f"Prepared to update existing user: {user.id}")
                else:
                    new_user = User(**user_data)
                    users_to_create.append(new_user)
                    remaining_requests = getattr(new_user, 'remaining_requests', None)
                    setattr(new_user, 'remaining_requests', max(user_data['remaining_requests'], int(remaining_requests) if remaining_requests is not None else 0))
                    setattr(new_user, 'last_request', data_time)
                    logger.debug(f"Prepared to create new user: {new_user.id}")

            # Prepare usages for bulk upsert
            usages_to_update = []
            usages_to_create = []
            for user_id, usage_data in usage_records.items():
                if user_id in existing_usages:
                    usage = existing_usages[user_id]
                    current_requests = getattr(usage, 'requests_today', 0) or 0
                    new_requests = min(int(usage_data['requests_today']), int(current_requests))
                    setattr(usage, 'requests_today', new_requests)

                    current_remaining = getattr(usage, 'remaining_requests', 0) or 0
                    new_remaining = max(int(usage_data['remaining_requests']), int(current_remaining))
                    setattr(usage, 'remaining_requests', new_remaining)

                    setattr(usage, 'last_reset', usage_data['last_reset'])
                    usage.last_request = usage_data['last_request']
                    usage.tier = usage_data['tier']
                    usage.ip_address = usage_data['ip_address']
                    usages_to_update.append(usage)
                    logger.debug(f"Prepared to update existing usage for user_id={user_id}")
                else:
                    new_usage = Usage(**usage_data)
                    usages_to_create.append(new_usage)
                    logger.debug(f"Prepared to create new usage for user_id={new_usage.user_id}")

            # Bulk save users and usages
            if users_to_create:
                db.add_all(users_to_create)
                logger.debug(f"Added {len(users_to_create)} new users.")
            if users_to_update:
                for user in users_to_update:
                    db.add(user)
                logger.debug(f"Updated {len(users_to_update)} existing users.")

            if usages_to_create:
                db.add_all(usages_to_create)
                logger.debug(f"Added {len(usages_to_create)} new usages.")
            if usages_to_update:
                for usage in usages_to_update:
                    db.add(usage)
                logger.debug(f"Updated {len(usages_to_update)} existing usages.")

            await db.commit()
            logger.debug("Committed user and usage records.")

            logger.info("Redis data synced to database successfully")

        except Exception as ex:
            logger.error(f"Error syncing Redis data to database: {str(ex)}", exc_info=True)
            raise

        finally:
            try:
                await db.close()
            except Exception:
                pass

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
                    if user.username is not None:
                        mapping["username"] = user.username
                    if user.tier is not None:
                        mapping["tier"] = user.tier
                    # if user.api_key:
                    #     mapping["api_key"] = user.api_key

                    if mapping:
                        logger.debug(f"Syncing user: {user.username} with ID: {user.id}")
                        pipe.hset(key, mapping=mapping)
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
                    key = self._get_key(str(usage.user_id), str(usage.ip_address))
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
                    pipe.hset(key, mapping=mapping)
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
                    result = self.redis.hdel(key, "active_token")
                    return bool(result)
                elif operation == "get":
                    result = self.redis.hget(key, "active_token")
                    return result.decode('utf-8') if isinstance(result, bytes) else result
                elif operation == "check":
                    stored_token = self.redis.hget(key, "active_token")
                    if stored_token and token:
                        return stored_token == token.encode('utf-8')
                    return False
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

    async def set_username_to_id_mapping(self, username: str, user_id: str) -> bool:
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
                    tracking_clients=info.get("tracking_clients", 0),
                    total_connections=info.get("total_connections", 0),
                    in_use_connections=len(self.redis.connection_pool._in_use_connections),
                )
        except Exception as ex:
            logger.error(f"Error getting connection stats: {str(ex)}")
            return RedisConnectionStats(
                connected_clients=0,
                blocked_clients=0,
                tracking_clients=0,
                total_connections=0,
                in_use_connections=0
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

            async with self.get_pipeline() as pipe:
                # Check each IP key
                for key in ip_keys:
                    key_type = await self.redis.type(key)
                    if key_type != b'hash':
                        logger.debug(f"Cleaning up IP key: {key}")
                        # If not a hash, delete it
                        await pipe.delete(key)

                # Check each user data key
                for key in user_keys:
                    key_type = await self.redis.type(key)
                    if key_type != b'hash':
                        logger.debug(f"Cleaning up user data key: {key}")
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
                str(priority): {
                    "queue_size": len(processor.operations),
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
                    "available_connections": len(pool._available_connections),
                    "total_connections": len(pool._in_use_connections) + len(pool._available_connections),
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
            # Create a dictionary of pending results if any exist
            pending_results = {"get_user_data": [batch_response]} if batch_response else {}
            await self.batch_processor._cleanup_pending_results(pending_results)


            await self.batch_processor._cleanup_pending_results(pending_results)


            await self.batch_processor._cleanup_pending_results(pending_results)



            await self.batch_processor._cleanup_pending_results(pending_results)

