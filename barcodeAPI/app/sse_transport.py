\
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

    def add_client(self, client_id: str, queue: asyncio.Queue[str]):
        """Registers a new SSE client and their message queue."""
        logger.info(f"Adding SSE client: {client_id}")
        self.active_clients[client_id] = queue

    def remove_client(self, client_id: str):
        """Unregisters an SSE client."""
        logger.info(f"Removing SSE client: {client_id}")
        # Ensure the queue consumer also stops if it's waiting on queue.get()
        queue = self.active_clients.pop(client_id, None)
        if queue:
            try:
                queue.put_nowait(None) # Sentinel to stop the event_generator loop
            except asyncio.QueueFull:
                logger.warning(f"Could not put sentinel in queue for client {client_id}, it might be full or already processed.")


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
            message_str = data.decode('utf-8')
            try:
                queue.put_nowait(message_str)
                logger.debug(f"Queued message for client {client_id}: {message_str[:200]}...")
            except asyncio.QueueFull:
                logger.error(f"SSE queue full for client {client_id}. Message dropped: {message_str[:200]}...")
            except Exception as e:
                logger.error(f"Error queuing message for client {client_id}: {e}")
        else:
            logger.warning(f"Client {client_id} not found in SseTransport. Message dropped: {data.decode('utf-8')[:200]}...")

    async def get_client_generator(self, client_id: str) -> Optional[AsyncGenerator[str, None]]:
        """
        Returns an async generator that yields messages for a specific client.
        This is not directly used by FastMCP but can be a utility for the SSE endpoint.
        """
        if client_id in self.active_clients:
            queue = self.active_clients[client_id]
            while True:
                message = await queue.get()
                if message is None:  # Sentinel for closing the connection
                    break
                yield message
                queue.task_done()
        else:
            logger.warning(f"Client generator requested for non-existent client: {client_id}")
            return None
