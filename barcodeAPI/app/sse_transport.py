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

    async def add_client(self, client_id: str, queue: asyncio.Queue[str]): # Made async
        """Registers a new SSE client and their message queue."""
        logger.info(f"Adding SSE client: {client_id}")
        self.active_clients[client_id] = queue

    async def remove_client(self, client_id: str): # Made async
        """Unregisters an SSE client."""
        logger.info(f"Removing SSE client: {client_id}")
        queue = self.active_clients.pop(client_id, None)
        if queue:
            try:
                # Internal logic remains synchronous for putting into queue
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
                message_str = data.decode('utf-8') # Moved inside try
                queue.put_nowait(message_str)
                logger.debug(f"Queued message for client {client_id}: {message_str[:200]}...")
            except asyncio.QueueFull:
                # Need message_str for this log, so decode must happen before or be duplicated.
                # For now, let's assume message_str might not be available if decode failed first.
                # Or, decode separately for logging if needed, but that's less clean.
                # The original code had message_str available here.
                # Let's decode again for the error message, or adjust log.
                # Safest is to log generic if message_str is not defined.
                log_msg_data = data.decode('utf-8', errors='replace')[:200] # Safely decode for logging
                logger.error(f"SSE queue full for client {client_id}. Message dropped: {log_msg_data}...")
            except UnicodeDecodeError as e: # Specifically catch decode errors
                logger.error(f"Error processing or queuing message for client {client_id}: {e}")
            except Exception as e:
                logger.error(f"Error processing or queuing message for client {client_id}: {e}") # Updated log message
        else:
            logger.warning(f"Client {client_id} not found in SseTransport. Message dropped: {data.decode('utf-8', errors='replace')[:200]}...")

    async def get_client_generator(self, client_id: str) -> AsyncGenerator[str, None]: # Changed Optional[...] to AsyncGenerator[...]
        """
        Returns an async generator that yields messages for a specific client.
        If the client_id is not found, it yields an empty generator.
        This is not directly used by FastMCP but can be a utility for the SSE endpoint.
        """
        if client_id in self.active_clients:
            queue = self.active_clients[client_id]
            while True:
                message = await queue.get()
                if message is None:  # Sentinel for closing the connection
                    break
                yield message
                queue.task_done() # Mark task as done for the queue
        else: # Client not found
            logger.warning(f"Client generator requested for non-existent client: {client_id}")
            # To make this an empty async generator, we need an async def that does nothing or yields nothing
            # The simplest way is to let this function complete if client_id not in self.active_clients,
            # and if it's an async generator function, it will return an empty async generator.
            # The current structure is fine; if not client_id in self.active_clients, it implicitly returns an empty async gen.
            # No 'return' statement is needed here for an empty async generator.
            # If we wanted to be explicit for an empty async gen, we could do:
            # if False: yield # This makes it a generator that yields nothing.
            # The current code already achieves this by not entering the loop.
            pass # Explicitly do nothing, will result in an empty async generator

    async def is_client_connected(self, client_id: str) -> bool:
        """Checks if a client_id is currently registered and active."""
        is_connected = client_id in self.active_clients
        logger.debug(f"Checking if client {client_id} is connected: {is_connected}")
        return is_connected
