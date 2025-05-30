# barcodeAPI/app/sse_transport.py
import asyncio
import logging
from typing import Dict, Optional, AsyncGenerator

logger = logging.getLogger(__name__)

class SseTransport:
    """
    A custom transport for FastMCP to handle message routing to multiple SSE clients.
    FastMCP's send_data method will call this transport's write method.
    """
    def __init__(self):
        self.active_clients: Dict[str, asyncio.Queue[str]] = {}
        logger.info("SseTransport initialized.")

    async def add_client(self, client_id: str, queue: asyncio.Queue[str]):
        """Registers a new SSE client and their message queue."""
        logger.info(f"Adding SSE client: {client_id}")
        self.active_clients[client_id] = queue

    async def remove_client(self, client_id: str):
        """Unregisters an SSE client."""
        logger.info(f"Removing SSE client: {client_id}")
        queue = self.active_clients.pop(client_id, None)
        if queue:
            try:
                queue.put_nowait(None)
                logger.debug(f"Sent None sentinel to queue for client {client_id} using put_nowait.")
            except asyncio.QueueFull:
                logger.warning(f"Could not put sentinel in queue for client {client_id} using put_nowait, queue full.")
            except Exception as e:
                logger.warning(f"Error putting sentinel in queue for client {client_id} using put_nowait: {e}")


    def write(self, data: bytes, client_id: Optional[str] = None):
        """
        Called by FastMCP (via JsonRpcServer.send_data) to send a message.
        The data is a serialized JSON-RPC message (bytes).
        It queues the message (as a string) for the specified client_id.
        """
        if not client_id:
            logger.error("SseTransport.write called without client_id. Message dropped.")
            return

        if client_id in self.active_clients:
            queue = self.active_clients[client_id]
            try:
                message_str = data.decode('utf-8')
                queue.put_nowait(message_str)
                logger.debug(f"Queued message for client {client_id}: {message_str[:200]}...")
            except asyncio.QueueFull:
                log_msg_data = data.decode('utf-8', errors='replace')[:200]
                logger.error(f"SSE queue full for client {client_id}. Message dropped: {log_msg_data}...")
            except UnicodeDecodeError as e:
                logger.error(f"Error processing or queuing message for client {client_id}: {e}")
            except Exception as e:
                logger.error(f"Error processing or queuing message for client {client_id}: {e}")
        else:
            logger.warning(f"Client {client_id} not found in SseTransport. Message dropped: {data.decode('utf-8', errors='replace')[:200]}...")

    async def get_client_generator(self, client_id: str) -> AsyncGenerator[str, None]:
        """
        Returns an async generator that yields messages for a specific client.
        If the client_id is not found, it yields an empty generator.
        This is not directly used by FastMCP but can be a utility for the SSE endpoint.
        """
        if client_id in self.active_clients:
            queue = self.active_clients[client_id]
            while True:
                message = await queue.get()
                if message is None:
                    break
                yield message
                queue.task_done()
        else: # Client not found
            logger.warning(f"Client generator requested for non-existent client: {client_id}")
            pass # Explicitly do nothing, will result in an empty async generator

    async def is_client_connected(self, client_id: str) -> bool:
        """Checks if a client_id is currently registered and active."""
        is_connected = client_id in self.active_clients
        logger.debug(f"Checking if client {client_id} is connected: {is_connected}")
        return is_connected
