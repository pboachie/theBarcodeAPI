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

    async def add_to_batch(self, operation: str, item: Any) -> Any:
        """Add an item to the batch for processing"""
        async with self.lock:
            self.batch.append((operation, item))
            if len(self.batch) >= self.batch_size:
                return await self._process_batch()
            return item

    async def _process_batches(self):
        while True:
            try:
                if self.batch:
                    async with self.lock:
                        await self._process_batch()
            except Exception as ex:
                logger.error(f"Error in _process_batches: {str(ex)}")
            await asyncio.sleep(self.interval)

    async def _process_batch(self):
        if not self.batch:
            return []

        current_batch = self.batch
        self.batch = []
        results = []

        for operation, item in current_batch:
            try:
                # Process based on operation type
                if operation == "get_user_data":
                    user_id, ip_address = item
                    # Implement actual user data fetching logic here
                    results.append({"id": user_id, "ip_address": ip_address})
                else:
                    results.append(item)
            except Exception as ex:
                logger.error(f"Error processing batch item: {str(ex)}")
                results.append(None)

        return results

class MultiLevelBatchProcessor:
    def __init__(self, redis_manager):
        self.redis_manager = redis_manager
        self.processors = {
            BatchPriority.HIGH: BatchProcessor(100, 1, redis_manager),
            BatchPriority.MEDIUM: BatchProcessor(100, 5, redis_manager),
            BatchPriority.LOW: BatchProcessor(100, 10, redis_manager)
        }
        self.tasks = []

    async def start(self):
        logger.info("Starting MultiLevelBatchProcessor...")
        for priority, processor in self.processors.items():
            task = asyncio.create_task(processor._process_batches())
            self.tasks.append(task)
        logger.info("MultiLevelBatchProcessor started.")

    async def stop(self):
        logger.info("Stopping MultiLevelBatchProcessor...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("MultiLevelBatchProcessor stopped.")

    async def add_to_batch(self, operation: str, item: Any, priority: BatchPriority = BatchPriority.MEDIUM) -> Any:
        logger.info(f"Adding to batch: priority={priority}, operation={operation}, item={item}")
        return await self.processors[priority].add_to_batch(operation, item)