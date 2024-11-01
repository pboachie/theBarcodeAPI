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

    async def _process_batch(self):
        """Process the current batch of operations"""
        if not self.batch:
            return

        current_batch = []
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
                    try:
                        # Process items concurrently for faster response
                        tasks = []
                        for (ip_address,), batch_id in items:
                            task = asyncio.create_task(self._process_single_item(ip_address, batch_id))
                            tasks.append(task)
                        await asyncio.gather(*tasks)

                    except Exception as ex:
                        logger.error(f"Error in get_user_data: {str(ex)}")
                        for (ip_address,), batch_id in items:
                            future = self.pending_results.get(batch_id)
                            if future and not future.done():
                                future.set_result(self.create_default_user_data(ip_address))

        except Exception as ex:
            logger.error(f"Error processing batch: {str(ex)}")
            for operation, item, batch_id in current_batch:
                future = self.pending_results.get(batch_id)
                if future and not future.done():
                    ip_address = item[0] if isinstance(item, tuple) else "unknown"
                    future.set_result(self.create_default_user_data(ip_address))

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
