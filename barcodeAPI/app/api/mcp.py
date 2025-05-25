# app/api/mcp.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import EventSourceResponse
from app.rate_limiter import rate_limit
from app.config import settings

import asyncio

router = APIRouter()
rate_limit_val = 10000 if settings.ENVIRONMENT == 'development' else 50

@router.get("/sse", response_class=EventSourceResponse)
@rate_limit(times=rate_limit_val, interval=1, period="second")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for remote MCP clients."""
    async def event_generator():
        while True:
            await asyncio.sleep(15)
            yield {"event": "keepalive", "data": "ping"}
            if await request.is_disconnected():
                break
    return EventSourceResponse(event_generator())
