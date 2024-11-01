# app/batch_processor.py

from enum import Enum
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from app.schemas import BatchPriority, UserData
import asyncio
import time
from asyncio import Lock, Task
import logging

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, batch_size, interval, redis_manager):
        self.batch_size = batch_size
        self.interval = interval
        self.redis_manager = redis_manager
        self.batch = []
        self.lock = Lock()
        self.pending_results = {}
        self.current_batch_id = 0

    async def add_to_batch(self, operation: str, item: Any) -> Any:
        """Add an item to the batch for processing and return a future for the result"""
        async with self.lock:
            batch_item_id = f"{self.current_batch_id}_{len(self.batch)}"
            future = asyncio.Future()
            self.pending_results[batch_item_id] = future
            self.batch.append((operation, item, batch_item_id))

            if len(self.batch) >= self.batch_size:
                await self._process_batch()

            return await future

    async def _process_batches(self):
        """Continuously process batches at the specified interval"""
        while True:
            try:
                if self.batch:
                    async with self.lock:
                        await self._process_batch()
            except Exception as ex:
                logger.error(f"Error in _process_batches: {str(ex)}")
            await asyncio.sleep(self.interval)

    async def _process_batch(self):
        """Process the current batch of operations"""
        if not self.batch:
            return

        async with self.lock:
            current_batch = self.batch
            self.batch = []
            self.current_batch_id += 1

        # Group operations by type for efficient processing
        operation_groups = defaultdict(list)
        for operation, item, batch_id in current_batch:
            operation_groups[operation].append((item, batch_id))

        try:
            # Process each operation type in bulk
            for operation, items in operation_groups.items():
                if operation == "check_rate_limit":
                    # Bulk rate limit checking
                    keys = [item for item, _ in items]
                    async with self.redis_manager.get_connection():
                        pipe = self.redis_manager.redis.pipeline()
                        for key in keys:
                            pipe.get(f"rate_limit:{key}")
                        results = await pipe.execute()

                        for (_, batch_id), result in zip(items, results):
                            limit_reached = result is not None and int(result) >= self.redis_manager.settings.RATE_LIMIT
                            future = self.pending_results.pop(batch_id, None)
                            if future and not future.done():
                                future.set_result(not limit_reached)

                elif operation == "get_user_data":
                    # Bulk user data fetching
                    async with self.redis_manager.get_connection():
                        pipe = self.redis_manager.redis.pipeline()
                        for (user_id, ip_address), _ in items:
                            key = self.redis_manager._get_key(user_id, ip_address)
                            pipe.get(key)
                        results = await pipe.execute()

                        for ((user_id, ip_address), batch_id), result in zip(items, results):
                            user_data = None
                            if result:
                                try:
                                    user_data = UserData.parse_raw(result)
                                except Exception as ex:
                                    logger.error(f"Error parsing user data: {str(ex)}")

                            future = self.pending_results.pop(batch_id, None)
                            if future and not future.done():
                                future.set_result(user_data)

                elif operation == "increment_usage":
                    # Bulk usage increment using Lua script
                    async with self.redis_manager.get_connection():
                        pipe = self.redis_manager.redis.pipeline()
                        for (user_id, ip_address), _ in items:
                            await self.redis_manager.redis.evalsha(
                                self.redis_manager.increment_usage_sha,
                                0,
                                str(user_id) if user_id else "-1",
                                ip_address,
                                self.redis_manager.settings.RATE_LIMIT,
                                time.time()
                            )
                        results = await pipe.execute()

                        for ((_, _), batch_id), result in zip(items, results):
                            future = self.pending_results.pop(batch_id, None)
                            if future and not future.done():
                                future.set_result(result)

        except Exception as ex:
            logger.error(f"Error processing batch: {str(ex)}")
            # Handle errors for any remaining futures
            for _, _, batch_id in current_batch:
                future = self.pending_results.pop(batch_id, None)
                if future and not future.done():
                    future.set_exception(ex)

class MultiLevelBatchProcessor:
    def __init__(self, redis_manager):
        self.redis_manager = redis_manager
        self.processors = {
            BatchPriority.HIGH: BatchProcessor(50, 1, redis_manager),    # Process every 1 second
            BatchPriority.MEDIUM: BatchProcessor(100, 2, redis_manager), # Process every 2 seconds
            BatchPriority.LOW: BatchProcessor(200, 3, redis_manager)    # Process every 3 seconds
        }
        self.tasks = []

    async def start(self):
        """Start all batch processors"""
        logger.info("Starting MultiLevelBatchProcessor...")
        for priority, processor in self.processors.items():
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