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
        self.last_process_time = time.time()
        self.max_wait_time = interval  # Maximum time to wait before processing a partial batch

    async def add_to_batch(self, operation: str, item: Any) -> Any:
        """Add an item to the batch for processing and return a future for the result"""
        try:
            current_time = time.time()
            async with self.lock:
                batch_item_id = f"{self.current_batch_id}_{len(self.batch)}"
                logger.info(f"Adding to batch: operation={operation}, item={item}, batch_item_id={batch_item_id}")
                future = asyncio.Future()
                self.pending_results[batch_item_id] = future
                self.batch.append((operation, item, batch_item_id))

                should_process = False
                # Check if batch is full
                if len(self.batch) >= self.batch_size:
                    logger.info("Batch full, processing...")
                    should_process = True
                # Check if max wait time has elapsed
                elif current_time - self.last_process_time >= self.max_wait_time and self.batch:
                    logger.info("Max wait time reached, processing partial batch...")
                    should_process = True

                if should_process:
                    await self._process_batch()
                    self.last_process_time = current_time

            try:
                result = await future
                logger.info(f"Received result for batch_item_id={batch_item_id}: {result}")
                return result
            except Exception as ex:
                logger.error(f"Error awaiting future: {str(ex)}")
                async with self.lock:
                    logger.info(f"Removing pending result: {batch_item_id}")
                    self.pending_results.pop(batch_item_id, None)
                raise
        except Exception as ex:
            logger.error(f"Error adding to batch: {str(ex)}")
            return None

    async def _process_batches(self):
        """Continuously process batches at the specified interval"""
        while True:
            try:
                current_time = time.time()
                if self.batch and (current_time - self.last_process_time >= self.interval):
                    async with self.lock:
                        logger.info(f"Processing partial batch of size {len(self.batch)} after interval")
                        await self._process_batch()
                        self.last_process_time = current_time
            except Exception as ex:
                logger.error(f"Error in _process_batches: {str(ex)}")
            await asyncio.sleep(min(self.interval, 1.0))  # Check more frequently but respect interval

    async def _process_batch(self):
        """Process the current batch of operations"""
        if not self.batch:
            logger.info("No batch to process.")
            return

        async with self.lock:
            current_batch = self.batch
            self.batch = []
            self.current_batch_id += 1
            logger.info(f"Processing batch: {current_batch}")

        # Group operations by type for efficient processing
        operation_groups = defaultdict(list)
        for operation, item, batch_id in current_batch:
            operation_groups[operation].append((item, batch_id))
        logger.info(f"Length of operation_groups: {len(operation_groups)}")

        try:
            # Process each operation type in bulk
            for operation, items in operation_groups.items():
                if operation == "check_rate_limit":
                    logger.info("Checking rate limit...")
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
                    logger.info("Getting user data...")
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
                    logger.info("Incrementing usage...")
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
            logger.info(f"Starting {priority.name} priority batch processor...")
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
        logger.info(f"Adding to {priority.name} priority batch: operation={operation}, item={item}")
        return await self.processors[priority].add_to_batch(operation, item)