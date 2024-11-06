from enum import Enum
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from app.schemas import BatchPriority, UserData
from app.config import settings
import asyncio
import time
from asyncio import Lock, Task
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, batch_size, interval_ms, redis_manager):
        self.batch_size = batch_size
        self.interval = interval_ms / 1000.0
        self.redis_manager = redis_manager
        self.batch = []
        self.pending_results = {}
        self.current_batch_id = 0
        self.last_process_time = time.time()
        self.max_wait_time = self.interval
        self.processing = False
        self._processing_lock = Lock()
        self._batch_lock = Lock()
        logger.info(f"Initialized BatchProcessor with size={batch_size}, interval={interval_ms}ms ({self.interval:.3f}s)")

    def _handle_batch_error(self, current_batch: List[Tuple[str, Any, str]]):
        """Handle errors for different types of batch operations"""
        for operation, item, batch_id in current_batch:
            future = self.pending_results.get(batch_id)
            if not future or future.done():
                continue

            try:
                # Set appropriate default values based on operation type
                if operation == "check_rate_limit":
                    # Default to rate limited for safety
                    future.set_result(False)

                elif operation == "is_token_active":
                    # Default to invalid token for safety
                    future.set_result(False)

                elif operation == "get_active_token":
                    # Default to no token
                    future.set_result(None)

                elif operation == "set_user_data":
                    # Default to operation failed
                    future.set_result(False)

                elif operation == "set_username_mapping":
                    # Default to operation failed
                    future.set_result(False)

                elif operation == "reset_daily_usage":
                    # Default to operation failed
                    future.set_result(False)

                elif operation in ["get_user_data", "get_user_data_by_ip", "increment_usage"]:
                    # For user data operations, extract IP address and return default user data
                    if isinstance(item, tuple):
                        ip_address = item[1] if len(item) > 1 else "unknown"
                    elif isinstance(item, dict):
                        ip_address = item.get('ip_address', "unknown")
                    else:
                        ip_address = str(item)

                    future.set_result(self.redis_manager.create_default_user_data(ip_address))

                else:
                    logger.error(f"Unknown operation type in error handler: {operation}")
                    future.set_result(None)

            except Exception as ex:
                logger.error(f"Error in batch error handler for operation {operation}: {str(ex)}")
                try:
                    future.set_result(None)
                except Exception:
                    pass

            finally:
                # Clean up the pending result
                self.pending_results.pop(batch_id, None)


    async def _process_batches(self):
        """Continuously process batches at the specified interval"""
        logger.info(f"Starting batch processor with interval {self.interval:.3f}s")
        while True:
            try:
                # Use shorter sleep intervals for more precise timing
                if self.interval <= 0.05:  # For urgent priority
                    await asyncio.sleep(0.01)  # Check more frequently
                else:
                    await asyncio.sleep(min(self.interval / 4, 0.05))

                if not self.batch or self.processing:
                    continue

                current_time = time.time()
                if current_time - self.last_process_time >= self.interval:
                    if not self.processing:
                        self.processing = True
                        try:
                            await self._process_batch()
                        finally:
                            self.processing = False
                            self.last_process_time = current_time

            except Exception as ex:
                logger.error(f"Error in _process_batches: {str(ex)}")
                await asyncio.sleep(0.01)  # Short recovery sleep

    async def add_to_batch(self, operation: str, item: Any) -> Any:
        """Add an item to the batch for processing and return a future for the result"""
        start_time = time.time()
        try:
            async with self._batch_lock:
                batch_item_id = f"{self.current_batch_id}_{len(self.batch)}"
                logger.debug(f"Adding to batch: operation={operation}, item={item}, batch_item_id={batch_item_id}")

                future = asyncio.Future()
                self.pending_results[batch_item_id] = future
                self.batch.append((operation, item, batch_item_id))

                # For URGENT priority, process immediately if we have items
                should_process = (
                    len(self.batch) >= self.batch_size or
                    (self.interval <= 0.05 and len(self.batch) > 0)  # Process immediately for urgent priority
                )

            if should_process and not self.processing:
                self.processing = True
                try:
                    await self._process_batch()
                finally:
                    self.processing = False
                    self.last_process_time = time.time()

            try:
                # Shorter timeout for urgent priority
                timeout = min(self.interval * 2, 0.1) if self.interval <= 0.05 else self.interval * 2
                result = await asyncio.wait_for(future, timeout=timeout)
                process_time = (time.time() - start_time) * 1000
                logger.debug(f"Request processed in {process_time:.2f}ms")
                return result
            except (asyncio.TimeoutError, Exception) as ex:
                logger.error(f"Error waiting for result: {str(ex)}")
                ip_address = item[0] if isinstance(item, tuple) else "unknown"
                return self.create_default_user_data(ip_address)
            finally:
                self.pending_results.pop(batch_item_id, None)

        except Exception as ex:
            logger.error(f"Error in add_to_batch: {str(ex)}")
            ip_address = item[0] if isinstance(item, tuple) else "unknown"
            return self.create_default_user_data(ip_address)

    async def _process_get_user_data(self, items):
        """Process batch of get_user_data operations"""
        try:
            tasks = []
            for (ip_address,), batch_id in items:
                task = asyncio.create_task(self._get_single_user_data(ip_address, batch_id))
                tasks.append(task)
            await asyncio.gather(*tasks)
        except Exception as ex:
            logger.error(f"Error in get_user_data batch: {str(ex)}")
            for (ip_address,), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(self.redis_manager.create_default_user_data(ip_address))

    async def _get_single_user_data(self, ip_address: str, batch_id: str):
        """Process a single get_user_data request"""
        try:
            ip_address = str(ip_address)
            key = self.redis_manager._get_key(None, ip_address)
            result = await self.redis_manager.redis.get(key)

            future = self.pending_results.get(batch_id)
            if future and not future.done():
                if result:
                    try:
                        user_data = UserData.parse_raw(result)
                        future.set_result(user_data)
                    except Exception:
                        future.set_result(self.redis_manager.create_default_user_data(ip_address))
                else:
                    future.set_result(self.redis_manager.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error getting user data: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(self.redis_manager.create_default_user_data(ip_address))


    async def _process_batch(self):
        """Process the current batch of operations"""
        if not self.batch:
            return

        current_batch = []
        start_time = time.time()
        try:
            async with self._batch_lock:
                current_batch = self.batch.copy()
                self.batch = []
                self.current_batch_id += 1

            operation_groups = defaultdict(list)
            for operation, item, batch_id in current_batch:
                operation_groups[operation].append((item, batch_id))

            for operation, items in operation_groups.items():
                logger.debug(f"Processing operation group: {operation} with {len(items)} items")

                if operation == "get_user_data":
                    await self._process_get_user_data(items)
                elif operation == "increment_usage":
                    await self._process_increment_usage(items)
                elif operation == "check_rate_limit":
                    await self._process_check_rate_limit(items)
                elif operation == "is_token_active":
                    await self._process_token_checks(items)
                elif operation == "get_active_token":
                    await self._process_get_tokens(items)
                elif operation == "set_user_data":
                    await self._process_set_user_data(items)
                elif operation == "reset_daily_usage":
                    await self._process_reset_daily_usage(items)
                elif operation == "set_username_mapping":
                    await self._process_username_mappings(items)
                elif operation == "get_user_data_by_ip":
                    await self._process_get_user_data_by_ip(items)
                else:
                    logger.warning(f"Unknown operation type: {operation}")

            # Log processing time for monitoring
            process_time = (time.time() - start_time) * 1000
            logger.debug(f"Batch processed in {process_time:.2f}ms")


        except Exception as ex:
            logger.error(f"Error processing batch: {str(ex)}\n{traceback.format_exc()}")
            self._handle_batch_error(current_batch)

    async def _process_set_user_data(self, items):
        """Process batch of set user data operations"""
        try:
            pipe = self.redis_manager.redis.pipeline()
            for (user_data,), batch_id in items:
                key = self.redis_manager._get_key(user_data.id, user_data.ip_address)
                pipe.set(key, user_data.json(), ex=86400)

            results = await pipe.execute()

            for i, ((_, ), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(results[i])
        except Exception as ex:
            logger.error(f"Error in set_user_data batch: {str(ex)}")
            for (_, ), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(False)

    async def _process_reset_daily_usage(self, items):
        """Process batch of reset daily usage operations"""
        try:
            pipe = self.redis_manager.redis.pipeline()
            update_tasks = []

            for (key,), batch_id in items:
                update_tasks.append(self._reset_single_usage(pipe, key, batch_id))

            await asyncio.gather(*update_tasks)
            results = await pipe.execute()

            for i, ((_, ), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(results[i])
        except Exception as ex:
            logger.error(f"Error in reset_daily_usage batch: {str(ex)}")
            for (_, ), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(False)

    async def _reset_single_usage(self, pipe, key: str, batch_id: str):
        """Reset usage for a single key"""
        try:
            result = await self.redis_manager.redis.get(key)
            if result:
                user_data = UserData.parse_raw(result)
                user_data.requests_today = 0
                pipe.set(key, user_data.json(), ex=86400)
        except Exception as ex:
            logger.error(f"Error resetting usage for key {key}: {str(ex)}")

    async def _process_username_mappings(self, items):
        """Process batch of username to ID mapping operations"""
        try:
            pipe = self.redis_manager.redis.pipeline()
            for (username, user_id), batch_id in items:
                pipe.set(f"user_data:{username}:username", user_id)

            results = await pipe.execute()

            for i, ((_, _), batch_id) in enumerate(items):
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(results[i])
        except Exception as ex:
            logger.error(f"Error in username mapping batch: {str(ex)}")
            for (_, _), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(False)

    async def _process_get_user_data_by_ip(self, items):
        """Process batch of get user data by IP operations"""
        try:
            tasks = []
            for (ip_address,), batch_id in items:
                task = asyncio.create_task(self._get_single_user_data_by_ip(ip_address, batch_id))
                tasks.append(task)
            await asyncio.gather(*tasks)
        except Exception as ex:
            logger.error(f"Error in get_user_data_by_ip batch: {str(ex)}")
            for (ip_address,), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(self.redis_manager.create_default_user_data(ip_address))

    async def _get_single_user_data_by_ip(self, ip_address: str, batch_id: str):
        """Get user data for a single IP"""
        try:
            key = f"ip:{ip_address}"
            result = await self.redis_manager.redis.get(key)

            future = self.pending_results.get(batch_id)
            if future and not future.done():
                if result:
                    try:
                        user_data = UserData.parse_raw(result)
                        full_data = await self._get_single_user_data(user_data.ip_address, f"{batch_id}_full")
                        future.set_result(full_data)
                    except Exception:
                        future.set_result(self.redis_manager.create_default_user_data(ip_address))
                else:
                    future.set_result(self.redis_manager.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error getting user data by IP: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(self.redis_manager.create_default_user_data(ip_address))


    async def _process_check_rate_limit(self, items):
        """Process batch of rate limit checks"""
        try:
            tasks = []
            for (key,), batch_id in items:
                task = asyncio.create_task(self._check_single_rate_limit(key, batch_id))
                tasks.append(task)
            await asyncio.gather(*tasks)
        except Exception as ex:
            logger.error(f"Error in check_rate_limit batch: {str(ex)}")
            for (key,), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(False)

    async def _process_increment_usage(self, items):
        """Process batch of usage increments"""
        try:
            tasks = []
            for (user_id, ip_address), batch_id in items:
                task = asyncio.create_task(
                    self._increment_single_usage(user_id, str(ip_address), batch_id)
                )
                tasks.append(task)
            await asyncio.gather(*tasks)
        except Exception as ex:
            logger.error(f"Error in increment_usage batch: {str(ex)}")
            for (_, ip_address), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(self.redis_manager.create_default_user_data(ip_address))

    async def _process_token_checks(self, items):
        """Process batch of token validity checks"""
        try:
            tasks = []
            for (user_id, token), batch_id in items:
                task = asyncio.create_task(self._check_single_token(user_id, token, batch_id))
                tasks.append(task)
            await asyncio.gather(*tasks)
        except Exception as ex:
            logger.error(f"Error in token checks batch: {str(ex)}")
            for (_, _), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(False)

    async def _process_get_tokens(self, items):
        """Process batch of token retrievals"""
        try:
            tasks = []
            for (user_id,), batch_id in items:
                task = asyncio.create_task(self._get_single_token(user_id, batch_id))
                tasks.append(task)
            await asyncio.gather(*tasks)
        except Exception as ex:
            logger.error(f"Error in get tokens batch: {str(ex)}")
            for (_, _), batch_id in items:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    future.set_result(None)

    # Helper methods for individual processing
    async def _check_single_rate_limit(self, key: str, batch_id: str):
        """Process a single rate limit check"""
        try:
            result = await self.redis_manager.redis.get(key)
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(bool(result))
        except Exception as ex:
            logger.error(f"Error checking rate limit: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(False)

    async def _increment_single_usage(self, user_id: Optional[int], ip_address: str, batch_id: str):
        """Process a single increment usage request"""
        try:
            ip_address = str(ip_address)  # Ensure ip_address is string
            rate_limit = settings.RateLimit.get_limit("unauthenticated")
            current_time = datetime.now(pytz.utc).isoformat()
            user_id_str = str(user_id) if user_id else "-1"

            result = await self.redis_manager.redis.evalsha(
                self.redis_manager.increment_usage_sha,
                0,
                user_id_str,
                ip_address,
                rate_limit,
                current_time,
            )

            future = self.pending_results.get(batch_id)
            if future and not future.done():
                try:
                    user_data = UserData.parse_raw(result)
                    future.set_result(user_data)
                except Exception as parse_ex:
                    logger.error(f"Error parsing user data: {str(parse_ex)}")
                    future.set_result(self.redis_manager.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error incrementing usage: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(self.redis_manager.create_default_user_data(ip_address))

    async def _check_single_token(self, user_id: int, token: str, batch_id: str):
        """Process a single token check"""
        try:
            stored_token = await self.redis_manager.redis.get(f"user_data:{user_id}:active_token")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(stored_token == token)
        except Exception as ex:
            logger.error(f"Error checking token: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(False)

    async def _get_single_token(self, user_id: int, batch_id: str):
        """Process a single token retrieval"""
        try:
            token = await self.redis_manager.redis.get(f"user_data:{user_id}:active_token")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(token)
        except Exception as ex:
            logger.error(f"Error getting token: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(None)

    async def _process_single_item(self, ip_address: str, batch_id: str):
        """Process a single item concurrently"""
        try:
            key = self.redis_manager._get_key(None, ip_address)
            result = await self.redis_manager.redis.get(key)

            future = self.pending_results.get(batch_id)
            if future and not future.done():
                if result:
                    try:
                        user_data = UserData.parse_raw(result)
                        future.set_result(user_data)
                    except Exception:
                        future.set_result(self.create_default_user_data(ip_address))
                else:
                    future.set_result(self.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error processing item: {str(ex)}")
            future = self.pending_results.get(batch_id)
            if future and not future.done():
                future.set_result(self.create_default_user_data(ip_address))

    def create_default_user_data(self, ip_address: str = "unknown") -> UserData:
        """Create a default UserData object"""
        return UserData(
            id=-1,
            username=f"ip:{ip_address}",
            ip_address=ip_address,
            tier="unauthenticated",
            remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
            requests_today=0,
            last_reset=datetime.now(pytz.utc)
        )

class MultiLevelBatchProcessor:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MultiLevelBatchProcessor, cls).__new__(cls)
        return cls._instance

    def __init__(self, redis_manager):
        if not hasattr(self, 'initialized'):
            self.redis_manager = redis_manager
            # Create separate processor instances for each priority
            self.processors = {
                BatchPriority.URGENT: BatchProcessor(25, 50, redis_manager),     # 50ms interval
                BatchPriority.HIGH: BatchProcessor(50, 500, redis_manager),      # 500ms interval
                BatchPriority.MEDIUM: BatchProcessor(100, 1000, redis_manager),  # 1 second interval
                BatchPriority.LOW: BatchProcessor(200, 2000, redis_manager)      # 2 second interval
            }
            self.tasks = []
            self.initialized = True
            logger.info("Initialized MultiLevelBatchProcessor with distinct intervals per priority")

    async def start(self):
        """Start all batch processors"""
        logger.info("Starting MultiLevelBatchProcessor...")
        for priority, processor in self.processors.items():
            interval_ms = int(processor.interval * 1000)
            logger.debug(f"Starting {priority.name} priority batch processor with {interval_ms}ms interval...")
            task = asyncio.create_task(processor._process_batches())
            self.tasks.append(task)
        logger.info("MultiLevelBatchProcessor started.")

    async def stop(self):
        """Stop all batch processors"""
        logger.info("Stopping MultiLevelBatchProcessor...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("MultiLevelBatchProcessor stopped.")

    async def add_to_batch(self, operation: str, item: Any, priority: BatchPriority = BatchPriority.MEDIUM) -> Any:
        """Add an item to the appropriate priority batch"""
        logger.debug(f"Adding to {priority.name} priority batch: operation={operation}, item={item}")
        return await self.processors[priority].add_to_batch(operation, item)
