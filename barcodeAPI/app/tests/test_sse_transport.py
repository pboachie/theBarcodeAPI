import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from app.sse_transport import SseTransport

# Configure logging for testing if necessary, or rely on caplog
# logging.basicConfig(level=logging.DEBUG)

@pytest.fixture
def transport():
    """Provides a fresh SseTransport instance for each test."""
    return SseTransport()

@pytest.mark.asyncio
async def test_add_client(transport: SseTransport):
    """Test adding a client."""
    client_id = "client1"
    queue = asyncio.Queue()
    await transport.add_client(client_id, queue)
    assert client_id in transport.active_clients
    assert transport.active_clients[client_id] is queue

@pytest.mark.asyncio
async def test_remove_client_successful(transport: SseTransport):
    """Test successful removal of a client."""
    client_id = "client_remove_success"
    queue = asyncio.Queue()
    await transport.add_client(client_id, queue)
    
    await transport.remove_client(client_id)
    
    assert client_id not in transport.active_clients
    # Check that None (sentinel) was put into the queue
    try:
        sentinel = queue.get_nowait()
        assert sentinel is None
    except asyncio.QueueEmpty:
        pytest.fail("Queue was empty, None sentinel not found.")

@pytest.mark.asyncio
async def test_remove_client_not_exists(transport: SseTransport, caplog):
    """Test removing a non-existent client."""
    client_id = "client_not_exists"
    initial_clients = transport.active_clients.copy()
    
    with caplog.at_level(logging.INFO): # SseTransport logs at INFO for removal
        await transport.remove_client(client_id)
    
    assert transport.active_clients == initial_clients
    # Check that no warning/error for trying to pop a non-existent client from dict,
    # but the method itself logs an INFO message.
    assert f"Removing SSE client: {client_id}" in caplog.text 
    # Check that no error or warning is logged about failing to pop from active_clients (it handles gracefully)

@pytest.mark.asyncio
async def test_remove_client_queue_full(transport: SseTransport, caplog):
    """Test removing a client when their queue is full (for the sentinel)."""
    client_id = "client_queue_full"
    # Queue that can hold 1 item, and we put an item, so put_nowait(None) would fail if queue was strictly typed and full
    # However, asyncio.Queue doesn't strictly block None based on maxsize if it's already full of other items.
    # The put_nowait(None) is what we are testing the handling of if it *were* to fail.
    queue = asyncio.Queue(maxsize=1)
    await queue.put("dummy_message") # Fill the queue
    
    await transport.add_client(client_id, queue)
    
    # Mock queue.put_nowait to simulate QueueFull exception
    # We need to mock the specific queue instance's method
    original_queue_instance = transport.active_clients[client_id]
    original_queue_instance.put_nowait = MagicMock(side_effect=asyncio.QueueFull)
            
    with caplog.at_level(logging.WARNING):
        await transport.remove_client(client_id)
        
    assert client_id not in transport.active_clients
    assert f"Could not put sentinel in queue for client {client_id} using put_nowait, queue full." in caplog.text

@pytest.mark.asyncio
async def test_is_client_connected(transport: SseTransport):
    """Test is_client_connected method."""
    client_id = "client_connect_test"
    queue = asyncio.Queue()
    
    assert not await transport.is_client_connected("non_existent_client")
    
    await transport.add_client(client_id, queue)
    assert await transport.is_client_connected(client_id)
    
    await transport.remove_client(client_id)
    assert not await transport.is_client_connected(client_id)

@pytest.mark.asyncio
async def test_write_client_exists(transport: SseTransport):
    """Test writing a message to an existing client."""
    client_id = "client_write_exists"
    queue = asyncio.Queue()
    await transport.add_client(client_id, queue)
    
    test_message = b"hello world"
    transport.write(test_message, client_id)
    
    try:
        queued_message = queue.get_nowait()
        assert queued_message == test_message.decode('utf-8')
    except asyncio.QueueEmpty:
        pytest.fail("Message was not found in client queue.")

@pytest.mark.asyncio
async def test_write_client_not_exists(transport: SseTransport, caplog):
    """Test writing a message to a non-existent client."""
    client_id = "client_write_not_exists"
    test_message = b"message_to_ghost"
    initial_clients_count = len(transport.active_clients)
    
    with caplog.at_level(logging.WARNING):
        transport.write(test_message, client_id)
        
    assert f"Client {client_id} not found in SseTransport. Message dropped" in caplog.text
    assert len(transport.active_clients) == initial_clients_count # No new client/queue created

@pytest.mark.asyncio
async def test_write_queue_full(transport: SseTransport, caplog):
    """Test writing a message to a client whose queue is full."""
    client_id = "client_write_queue_full"
    queue = asyncio.Queue(maxsize=1) # Max size of 1
    await transport.add_client(client_id, queue)
    
    # Fill the queue
    queue.put_nowait("first_message")
    
    test_message_bytes = b"overflow_message"
    test_message_str = test_message_bytes.decode('utf-8')

    with caplog.at_level(logging.ERROR):
        transport.write(test_message_bytes, client_id)
        
    assert f"SSE queue full for client {client_id}. Message dropped: {test_message_str[:200]}" in caplog.text
    
    # Verify the first message is still there, and the new one was not added
    try:
        assert queue.get_nowait() == "first_message"
    except asyncio.QueueEmpty:
        pytest.fail("Queue was unexpectedly empty.")
    
    assert queue.empty() # Should be empty now, as the overflow_message was not added

@pytest.mark.asyncio
async def test_write_no_client_id(transport: SseTransport, caplog):
    """Test writing a message without specifying a client_id."""
    test_message = b"message_to_nowhere"
    
    with caplog.at_level(logging.ERROR):
        transport.write(test_message) # No client_id provided
        
    assert "SseTransport.write called without client_id. Message dropped." in caplog.text

# Test for get_client_generator (optional, as it's a utility, not core to FastMCP interaction)
@pytest.mark.asyncio
async def test_get_client_generator_exists(transport: SseTransport):
    """Test get_client_generator for an existing client."""
    client_id = "client_gen_exists"
    queue = asyncio.Queue()
    await transport.add_client(client_id, queue)

    # Put some messages and a sentinel
    await queue.put("message1")
    await queue.put("message2")
    await queue.put(None) # Sentinel to stop generator

    messages = []
    # Corrected: get_client_generator is an async def, but the TypeError implies
    # we should not await it here if it's already behaving like a direct generator object
    # in the test context due to pytest-asyncio or other factors.
    client_gen = transport.get_client_generator(client_id)
    assert client_gen is not None, "get_client_generator should return a generator for existing client" # This assertion might still be relevant
    async for msg in client_gen: 
        messages.append(msg)
    
    assert messages == ["message1", "message2"]
    # After generator finishes, client should ideally be removed by SSE endpoint logic,
    # but get_client_generator itself doesn't remove. Here, queue.task_done() is called inside.

@pytest.mark.asyncio
async def test_get_client_generator_not_exists(transport: SseTransport, caplog):
    """Test get_client_generator for a non-existent client."""
    client_id = "client_gen_not_exists"
    messages_received = []
    with caplog.at_level(logging.WARNING):
        # Call to get the generator object (no await)
        gen_instance = transport.get_client_generator(client_id)
        # Iterate over it
        async for message in gen_instance:
            messages_received.append(message)
    
    assert not messages_received, "Generator for non-existent client should be empty"
    assert f"Client generator requested for non-existent client: {client_id}" in caplog.text

@pytest.mark.asyncio
async def test_remove_client_already_empty_queue(transport: SseTransport):
    """Test removing a client whose queue is already empty (put_nowait(None) should still succeed)."""
    client_id = "client_empty_queue_remove"
    queue = asyncio.Queue() # Empty queue
    await transport.add_client(client_id, queue)
    
    await transport.remove_client(client_id)
    
    assert client_id not in transport.active_clients
    try:
        sentinel = queue.get_nowait()
        assert sentinel is None, "Sentinel should be None"
    except asyncio.QueueEmpty:
        pytest.fail("Queue was empty, None sentinel should have been placed by remove_client.")

@pytest.mark.asyncio
async def test_remove_client_generic_exception_on_put(transport: SseTransport, caplog):
    """Test removing a client when queue.put_nowait raises an unexpected error."""
    client_id = "client_put_exception"
    queue = asyncio.Queue()
    await transport.add_client(client_id, queue)

    # Mock queue.put_nowait to simulate a generic error
    original_queue_instance = transport.active_clients[client_id]
    original_queue_instance.put_nowait = MagicMock(side_effect=RuntimeError("Unexpected error"))

    with caplog.at_level(logging.WARNING):
        await transport.remove_client(client_id)

    assert client_id not in transport.active_clients
    assert f"Error putting sentinel in queue for client {client_id} using put_nowait: Unexpected error" in caplog.text

@pytest.mark.asyncio
async def test_write_decode_error(transport: SseTransport, caplog):
    """Test SseTransport.write with data that cannot be UTF-8 decoded."""
    client_id = "client_decode_error"
    queue = asyncio.Queue()
    await transport.add_client(client_id, queue)

    invalid_utf8_bytes = b'\xff\xfe\xfd' # Invalid UTF-8 sequence

    # The decode error now happens in api/mcp.py or FastMCP, SseTransport.write expects bytes
    # and queues them after decoding. If decoding fails, it should be handled.
    # The current SseTransport.write decodes: message_str = data.decode('utf-8')
    # So, we expect a UnicodeDecodeError to be caught if it happens there.

    # Let's patch 'data.decode' for this specific call to simulate failure if not caught by write
    # However, it's better to test the actual behavior.
    # The current SseTransport.write has:
    #   message_str = data.decode('utf-8')
    #   queue.put_nowait(message_str)
    # If data.decode fails, it will raise UnicodeDecodeError before put_nowait.
    # The current SseTransport.write doesn't explicitly catch this.
    # This test will reveal that.
    
    # For the purpose of this test, let's assume the current implementation of `write`
    # does not have a try-except around `data.decode()`.
    # We expect the `write` method to fail with UnicodeDecodeError or be caught by its generic `except Exception`.
    # The current code has `except Exception as e: logger.error(f"Error queuing message for client {client_id}: {e}")`

    with caplog.at_level(logging.ERROR):
        transport.write(invalid_utf8_bytes, client_id)

    # Check if the generic exception handler in `write` caught the UnicodeDecodeError
    assert f"Error processing or queuing message for client {client_id}: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte" in caplog.text
    assert queue.empty(), "Queue should be empty if decoding/queuing failed."
