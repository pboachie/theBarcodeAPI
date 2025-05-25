# app/api/mcp.py
import asyncio
import uuid
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse # StreamingResponse added
from sse_starlette import EventSourceResponse # Can be kept or removed, not used by this endpoint now
from app.rate_limiter import rate_limit
from app.config import settings
import logging

# Initialize logger for this module
logger = logging.getLogger(__name__)

router = APIRouter()
rate_limit_val = 10000 if settings.ENVIRONMENT == 'development' else 50

@router.get("/sse") # Removed response_class=EventSourceResponse
@rate_limit(times=rate_limit_val, interval=1, period="second")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for remote MCP clients."""
    logger.debug("mcp_sse_endpoint: Entered function (Using StreamingResponse).")
    
    logger.debug("mcp_sse_endpoint: Before generating client_id.")
    client_id = uuid.uuid4().hex
    logger.debug(f"mcp_sse_endpoint: After generating client_id: {client_id}")
    
    try:
        logger.debug("mcp_sse_endpoint: Before getting sse_transport from app.state.")
        sse_transport = request.app.state.sse_transport
        logger.debug(f"mcp_sse_endpoint: After getting sse_transport: {type(sse_transport)}")
        # mcp_instance = request.app.state.mcp_instance # Not directly used here, but good to check startup
    except AttributeError as e:
        logger.error(f"mcp_sse_endpoint: sse_transport not found in app.state. Error: {e}", exc_info=True)
        async def error_event_generator_streaming(): # Renamed for clarity
            yield f"event: error\ndata: Server configuration error: SSE transport not available.\n\n"
        return StreamingResponse(error_event_generator_streaming(), media_type="text/event-stream")

    logger.debug("mcp_sse_endpoint: Before creating client_queue.")
    client_queue = asyncio.Queue() # Kept for now, though simplified generator doesn't use it.
    logger.debug(f"mcp_sse_endpoint: After creating client_queue: {type(client_queue)}")
    
    try:
        logger.debug(f"mcp_sse_endpoint: Before calling await sse_transport.add_client for client_id: {client_id}.")
        await sse_transport.add_client(client_id, client_queue) 
        logger.debug(f"mcp_sse_endpoint: After calling await sse_transport.add_client for client_id: {client_id}.")
        logger.info(f"SSE client {client_id} connected. Queue created.")
    except Exception as e:
        logger.error(f"mcp_sse_endpoint: Error during sse_transport.add_client for client_id {client_id}: {e}", exc_info=True)
        # Decide how to handle this - maybe return an error event immediately
        async def add_client_error_generator_streaming(): # Renamed for clarity
            yield f"event: error\ndata: Server error: Could not register client for SSE.\n\n"
        return StreamingResponse(add_client_error_generator_streaming(), media_type="text/event-stream")


    async def event_generator():
        nonlocal client_id # Ensure we use the outer scope client_id
        logger.debug(f"event_generator (StreamingResponse, client_id: {client_id}): Entered.")
        # Simplified generator: yields one client_id event string then returns
        yield f"event: client_id\ndata: {client_id}\n\n"
        logger.debug(f"event_generator (StreamingResponse, client_id: {client_id}): Yielded client_id event. Now returning.")
        return
        # Original loop and finally block remain commented out for this diagnostic step

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/mcp/cmd")
@rate_limit(times=rate_limit_val, interval=1, period="second")
async def mcp_command_endpoint(
    request: Request, 
    client_id: str = Header(..., alias="X-Client-ID", description="Client ID obtained from SSE connection")
):
    """MCP command endpoint for clients to send requests."""
    logger.debug(f"mcp_command_endpoint: Entered for client_id: {client_id}")
    try:
        logger.debug("mcp_command_endpoint: Attempting to access app.state.mcp_instance")
        mcp_instance = request.app.state.mcp_instance
        logger.debug("mcp_command_endpoint: Accessed app.state.mcp_instance")
        
        logger.debug("mcp_command_endpoint: Attempting to access app.state.sse_transport")
        sse_transport = request.app.state.sse_transport
        logger.debug("mcp_command_endpoint: Accessed app.state.sse_transport")
    except AttributeError:
        logger.error("mcp_instance or sse_transport not found in app.state. Ensure they are set during startup.")
        raise HTTPException(status_code=503, detail="Server not configured correctly (MCP or SSE transport missing).")

    if not client_id: # Should be caught by Header(...) but good practice
        raise HTTPException(status_code=400, detail="X-Client-ID header is required.")

    # Check if client is actively connected via SSE
    logger.debug(f"mcp_command_endpoint: Before calling sse_transport.is_client_connected for client_id: {client_id}")
    is_connected = await sse_transport.is_client_connected(client_id)
    logger.debug(f"mcp_command_endpoint: After sse_transport.is_client_connected, result: {is_connected}")
    if not is_connected: # Assumes is_client_connected is an async method
        logger.warning(f"Command received for disconnected or unknown client_id: {client_id}")
        raise HTTPException(status_code=404, detail=f"Client {client_id} not connected or unknown. Please establish SSE connection first.")

    logger.debug("mcp_command_endpoint: Before calling await request.body()")
    raw_request_body = await request.body()
    logger.debug("mcp_command_endpoint: After calling await request.body()")
    request_data_str = raw_request_body.decode('utf-8')
    logger.info(f"Received command for client {client_id}. Raw request: {request_data_str[:200]}...")

    # process_request in FastMCP (when a transport is set) will use the transport to send the response.
    # It's a coroutine, so we should await it or create a task.
    # Creating a task allows us to return 202 Accepted immediately.
    asyncio.create_task(mcp_instance.process_request(request_data_str, client_id=client_id))
    logger.debug(f"Task created for mcp_instance.process_request for client {client_id}")

    return JSONResponse({"status": "request_received", "client_id": client_id}, status_code=202)
