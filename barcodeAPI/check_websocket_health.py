#!/usr/bin/env python3
"""
Simple health check script for WebSocket connectivity in Docker
"""

import asyncio
import aiohttp
import sys

async def check_websocket_health():
    """Check if WebSocket MCP endpoint is available."""
    try:
        # First check the HTTP status endpoint
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8000/api/v1/mcp/status') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"WebSocket MCP status: {data}")
                    return True
                else:
                    print(f"WebSocket MCP status check failed: {resp.status}")
                    return False
    except Exception as e:
        print(f"WebSocket MCP health check failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(check_websocket_health())
    sys.exit(0 if result else 1)