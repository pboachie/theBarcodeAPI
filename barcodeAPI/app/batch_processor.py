import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging

from typing import Any, Dict, List, Optional
import time
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@dataclass
class BatchOperation:
    operation: str
    item: Any
    priority: str
    created_at: float
    future: asyncio.Future

class BatchProcessor:
    def __init__(self, redis_manager, batch_size=100, max_wait_time=0.5):
        self.redis_manager = redis_manager
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.operations: List[BatchOperation] = []
        self.processing = False
        self.running = False
        self.last_process_time = time.time()
        self._lock = asyncio.Lock()
        self._process_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the batch processor"""
        logger.info(f"Starting batch processor with batch size {self.batch_size}")
        if self.running:
            logger.warning("Batch processor already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Batch processor started and processing loop initialized")

        self.running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Batch processor started")

    async def stop(self):
        """Stop the batch processor"""
        if not self.running:
            return

        self.running = False
        self._process_event.set()  # Wake up the process loop
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self.max_wait_time)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        logger.info("Batch processor stopped")

    async def add_operation(self, operation: str, item: Any, priority: str) -> Any:
        """Add an operation to the batch with timeout handling"""
        if not self.running:
            raise RuntimeError("Batch processor is not running")

        future = asyncio.get_running_loop().create_future()
        batch_op = BatchOperation(
            operation=operation,
            item=item,
            priority=priority,
            created_at=time.time(),
            future=future
        )

        async with self._lock:
            self.operations.append(batch_op)
            if len(self.operations) >= self.batch_size:
                self._process_event.set()

        try:
            # Wait for result with timeout
            return await asyncio.wait_for(future, timeout=self.max_wait_time)
        except asyncio.TimeoutError:
            # Handle timeout by processing directly
            logger.warning(f"Operation {operation} timed out, processing directly")
            try:
                return await self._process_single_operation(batch_op)
            except Exception as e:
                logger.error(f"Direct processing failed: {e}", exc_info=True)
                return await self.redis_manager.get_default_value(operation, item)
        finally:
            # Clean up if operation wasn't processed
            async with self._lock:
                if batch_op in self.operations:
                    self.operations.remove(batch_op)
                    if not batch_op.future.done():
                        batch_op.future.cancel()

    async def _process_single_operation(self, operation: BatchOperation) -> Any:
        """Process a single operation directly"""
        async with self.redis_manager.get_pipeline() as pipe:
            results = {}
            await self.redis_manager.process_batch_operation(
                operation.operation,
                [(operation.item, id(operation))],
                pipe,
                {id(operation): operation.future}
            )
            if not operation.future.done():
                return await self.redis_manager.get_default_value(operation.operation, operation.item)
            return await operation.future

    async def _process_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                if not self.operations:
                    # Wait for new operations or shutdown
                    try:
                        await asyncio.wait_for(self._process_event.wait(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue
                    self._process_event.clear()
                    continue

                current_time = time.time()
                if (len(self.operations) >= self.batch_size or
                    current_time - self.last_process_time >= self.max_wait_time):
                    await self._process_batch()

            except Exception as e:
                logger.error(f"Error in process loop: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _process_batch(self):
        """Process a batch of operations"""
        async with self._lock:
            if not self.operations:
                return

            # Sort by priority and creation time
            self.operations.sort(
                key=lambda x: (x.priority, x.created_at)
            )

            current_batch = self.operations[:self.batch_size]
            self.operations = self.operations[self.batch_size:]

        if not current_batch:
            return

        # Group operations by type
        operation_groups: Dict[str, List[BatchOperation]] = {}
        for op in current_batch:
            operation_groups.setdefault(op.operation, []).append(op)

        # Process each operation group
        async with self.redis_manager.get_pipeline() as pipe:
            start_time = time.time()
            try:
                for operation, ops in operation_groups.items():
                    await self.redis_manager.process_batch_operation(
                        operation,
                        [(op.item, id(op)) for op in ops],
                        pipe,
                        {id(op): op.future for op in ops}
                    )

                self.last_process_time = time.time()
                process_time = (time.time() - start_time) * 1000
                logger.debug(f"Batch processed in {process_time:.2f}ms")

            except Exception as e:
                logger.error(f"Error processing batch: {e}", exc_info=True)
                # Set default values for all operations in the batch
                for op in current_batch:
                    if not op.future.done():
                        try:
                            default_value = await self.redis_manager.get_default_value(op.operation, op.item)
                            op.future.set_result(default_value)
                        except Exception as ex:
                            logger.error(f"Error setting default value: {ex}")
                            op.future.cancel()

    def __del__(self):
        """Cleanup on deletion"""
        for op in self.operations:
            if not op.future.done():
                op.future.cancel()
        self.operations.clear()


class MultiLevelBatchProcessor:
    def __init__(self, redis_manager):
        self.processors = {
            "URGENT": BatchProcessor(redis_manager, batch_size=25, max_wait_time=0.1),
            "HIGH": BatchProcessor(redis_manager, batch_size=100, max_wait_time=0.5),
            "MEDIUM": BatchProcessor(redis_manager, batch_size=200, max_wait_time=1.0),
            "LOW": BatchProcessor(redis_manager, batch_size=500, max_wait_time=2.0)
        }

    async def start(self):
        """Start all processors"""
        for processor in self.processors.values():
            await processor.start()

    async def stop(self):
        """Stop all processors"""
        for processor in self.processors.values():
            await processor.stop()

    async def add_to_batch(self, operation: str, item: Any, priority: str = "MEDIUM") -> Any:
        """Add operation to appropriate processor based on priority"""
        processor = self.processors.get(priority)
        if not processor:
            raise ValueError(f"Invalid priority: {priority}")

        return await processor.add_operation(operation, item, priority)