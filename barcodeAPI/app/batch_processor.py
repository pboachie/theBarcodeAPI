import asyncio
import gc
import logging
import time
import traceback
from asyncio import Lock, Task
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pytz

from app.config import settings
from app.schemas import BatchPriority, UserData

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, batch_size: int, interval_ms: int, redis_manager):
        self.batch_size = batch_size
        self.interval = interval_ms / 1000.0
        self.redis_manager = redis_manager
        self.batch = []
        self.pending_results = {}
        self.current_batch_id = 0
        self.last_process_time = time.time()
        self.processing = False
        self._stopping = False
        self._processing_lock = Lock()
        self._batch_lock = Lock()
        logger.info(f"Initialized BatchProcessor with size={batch_size}, interval={interval_ms}ms")

    @asynccontextmanager
    async def get_pipeline(self):
        """Context manager for Redis pipeline operations"""
        pipe = self.redis_manager.redis.pipeline()
        try:
            yield pipe
            await pipe.execute()
        except Exception as ex:
            logger.error(f"Pipeline error: {str(ex)}")
            raise
        finally:
            await pipe.reset()

    async def add_to_batch(self, operation: str, item: Any) -> Any:
        """Add an item to the batch for processing"""
        batch_item_id = f"{self.current_batch_id}_{len(self.batch)}"
        start_time = time.time()

        try:
            async with self._batch_lock:
                future = asyncio.Future()
                self.pending_results[batch_item_id] = future
                self.batch.append((operation, item, batch_item_id))

                should_process = (
                    len(self.batch) >= self.batch_size or
                    (self.interval <= 0.05 and len(self.batch) > 0)
                )

            if should_process and not self.processing:
                async with self._processing_lock:
                    await self._process_current_batch()

            timeout = min(self.interval * 2, 0.1) if self.interval <= 0.05 else self.interval * 2
            result = await asyncio.wait_for(future, timeout=timeout)
            process_time = (time.time() - start_time) * 1000
            logger.debug(f"Request processed in {process_time:.2f}ms")
            return result

        except (asyncio.TimeoutError, Exception) as ex:
            logger.error(f"Error in add_to_batch: {str(ex)}")
            return self.redis_manager.get_default_value(operation, item)
        finally:
            self._cleanup_future(batch_item_id)

    async def _process_current_batch(self):
        """Process the current batch of operations"""
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

            # Group operations
            operation_groups = self._group_operations(current_batch)

            # Use a single pipeline for the entire batch
            async with self.get_pipeline() as pipe:
                for operation, items in operation_groups.items():
                    logger.debug(f"Processing operation group: {operation} with {len(items)} items")
                    await self.redis_manager.process_batch_operation(operation, items, pipe, self.pending_results)

            process_time = (time.time() - start_time) * 1000
            logger.debug(f"Batch processed in {process_time:.2f}ms")

        except Exception as ex:
            logger.error(f"Error processing batch: {str(ex)}\n{traceback.format_exc()}")
            self._handle_batch_error(current_batch)
        finally:
            self.processing = False
            self.last_process_time = time.time()

    def _get_default_value(self, operation: str, item: Any = None) -> Any:
        """Get default value based on operation type"""
        return self.redis_manager.get_default_value(operation, item)

    def _handle_batch_error(self, batch: List[Tuple[str, Any, str]]):
        """Handle batch operation errors"""
        for operation, item, batch_id in batch:
            try:
                default_value = self.redis_manager.get_default_value(operation, item)
                self._cleanup_future(batch_id, default_value)
            except Exception as ex:
                logger.error(f"Error handling batch error: {str(ex)}")
                self._cleanup_future(batch_id, None)

    def _cleanup_future(self, batch_id: str, default_value: Any = None):
        """Safely cleanup a future with logging"""
        future = self.pending_results.get(batch_id)
        if future:
            try:
                if not future.done():
                    logger.debug(f"Setting result for batch_id {batch_id}: {default_value}")
                    future.set_result(default_value)
            except Exception as ex:
                logger.error(f"Error setting future result: {ex}")
                future.cancel()
            finally:
                self.pending_results.pop(batch_id, None)

    def _create_default_user_data(self, item: Any) -> UserData:
        """Create default user data based on item type"""
        ip_address = self.redis_manager._extract_ip_address(item)
        return self.redis_manager.create_default_user_data(ip_address)

    def _group_operations(self, batch: List[Tuple[str, Any, str]]) -> Dict[str, List[Tuple[Any, str]]]:
        """Group batch operations by type"""
        operation_groups = defaultdict(list)
        for operation, item, batch_id in batch:
            operation_groups[operation].append((item, batch_id))
        return operation_groups

    async def process_batches(self):
        """Main batch processing loop"""
        logger.info(f"Starting batch processor with interval {self.interval:.3f}s")
        while not self._stopping:
            try:
                sleep_time = min(self.interval / 4, 0.05) if self.interval > 0.05 else 0.01
                await asyncio.sleep(sleep_time)

                if not self.batch or self.processing:
                    continue

                current_time = time.time()
                if current_time - self.last_process_time >= self.interval:
                    async with self._processing_lock:
                        await self._process_current_batch()

            except Exception as ex:
                logger.error(f"Error in batch processing: {str(ex)}")
                await self._handle_batch_error(self.batch.copy())
                await asyncio.sleep(0.01)

    async def migrate_to_hash_structure(redis_manager):
        """Migrate existing Redis data to hash structure"""
        try:
            # Get all keys
            user_keys = await redis_manager.redis.keys("user_data:*")
            ip_keys = await redis_manager.redis.keys("ip:*")

            async with redis_manager.redis.pipeline() as pipe:
                # Migrate user data
                for key in user_keys:
                    try:
                        # Get existing data
                        old_data = await redis_manager.redis.get(key)
                        if old_data:
                            user_data = UserData.parse_raw(old_data)
                            # Convert to hash
                            pipe.hset(key, mapping={
                                "id": str(user_data.id),
                                "username": user_data.username,
                                "ip_address": user_data.ip_address,
                                "tier": user_data.tier,
                                "requests_today": str(user_data.requests_today),
                                "remaining_requests": str(user_data.remaining_requests),
                                "last_request": user_data.last_request.isoformat() if user_data.last_request else ""
                            })
                            pipe.expire(key, 86400)
                    except Exception as ex:
                        logger.error(f"Error migrating key {key}: {ex}")

                # Migrate IP data
                for key in ip_keys:
                    try:
                        old_data = await redis_manager.redis.get(key)
                        if old_data:
                            user_data = UserData.parse_raw(old_data)
                            pipe.hset(key, mapping={
                                "ip_address": user_data.ip_address,
                                "requests_today": str(user_data.requests_today),
                                "remaining_requests": str(user_data.remaining_requests),
                                "last_request": user_data.last_request.isoformat() if user_data.last_request else ""
                            })
                            pipe.expire(key, 86400)
                    except Exception as ex:
                        logger.error(f"Error migrating key {key}: {ex}")

                await pipe.execute()

            logger.info(f"Successfully migrated {len(user_keys) + len(ip_keys)} keys to hash structure")
        except Exception as ex:
            logger.error(f"Error during migration: {ex}")
            raise

    async def start(self):
        """Start batch processing"""
        self._stopping = False
        while not self._stopping:
            try:
                sleep_time = min(self.interval / 4, 0.05) if self.interval > 0.05 else 0.01
                await asyncio.sleep(sleep_time)

                if not self.batch or self.processing:
                    continue

                current_time = time.time()
                if current_time - self.last_process_time >= self.interval:
                    async with self._processing_lock:
                        await self._process_current_batch()

            except Exception as ex:
                logger.error(f"Error in batch processing: {str(ex)}")
                await asyncio.sleep(0.01)

    async def stop(self):
        """Stop batch processing and cleanup"""
        try:
            self._stopping = True

            # Cancel pending futures
            for batch_id, future in list(self.pending_results.items()):
                if not future.done():
                    future.cancel()
                self.pending_results.pop(batch_id, None)

            # Clear batch
            self.batch.clear()

            # Force cleanup
            gc.disable()  # Temporarily disable automatic collection
            try:
                # Collect all generations
                gc.collect()
                gc.collect(1)
                gc.collect(2)
            finally:
                gc.enable()

        except Exception as ex:
            logger.error(f"Error stopping batch processor: {ex}")
            # Ensure cleanup even on error
            self.pending_results.clear()
            self.batch.clear()

    def __del__(self):
        """Ensure cleanup on deletion"""
        try:
            # Cancel any remaining futures
            for future in self.pending_results.values():
                if not future.done():
                    future.cancel()
            self.pending_results.clear()
            self.batch.clear()
        except Exception:
            pass


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
            self.processors = {
                BatchPriority.URGENT: BatchProcessor(25, 50, redis_manager),
                BatchPriority.HIGH: BatchProcessor(50, 500, redis_manager),
                BatchPriority.MEDIUM: BatchProcessor(100, 1000, redis_manager),
                BatchPriority.LOW: BatchProcessor(200, 2000, redis_manager)
            }
            self.tasks = []
            self.initialized = True
            logger.info("Initialized MultiLevelBatchProcessor with priority-based intervals")

    async def start(self):
        """Start all priority-based processors"""
        logger.info("Starting MultiLevelBatchProcessor...")
        for priority, processor in self.processors.items():
            task = asyncio.create_task(processor.process_batches())  # Changed from _process_batches to process_batches
            self.tasks.append(task)
            logger.debug(f"Started {priority.name} priority processor with {int(processor.interval * 1000)}ms interval")
        logger.info("MultiLevelBatchProcessor started successfully")

    async def stop(self):
        """Stop all processors and cleanup"""
        logger.info("Stopping MultiLevelBatchProcessor...")
        try:
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()
            for processor in self.processors.values():
                await processor.stop()
            gc.collect()
            logger.info("MultiLevelBatchProcessor stopped successfully")
        except Exception as ex:
            logger.error(f"Error stopping MultiLevelBatchProcessor: {str(ex)}")

    async def add_to_batch(self, operation: str, item: Any, priority: BatchPriority = BatchPriority.MEDIUM) -> Any:
        """Add item to appropriate priority batch"""
        logger.debug(f"Adding to {priority.name} priority batch: operation={operation}, item={item}")
        return await self.processors[priority].add_to_batch(operation, item)
