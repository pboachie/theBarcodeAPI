#!/usr/bin/env python3
"""
Simple test script for WebSocket MCP functionality
"""

import asyncio
import websockets
import json

async def test_websocket_mcp():
    """Test basic MCP WebSocket functionality."""
    uri = "ws://localhost:8000/api/v1/mcp/ws/test-client"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket MCP endpoint")
            
            # Test initialize message
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.0.0",
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            await websocket.send(json.dumps(init_message))
            response = await websocket.recv()
            print(f"Initialize response: {response}")
            
            # Test tools list
            tools_message = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            await websocket.send(json.dumps(tools_message))
            response = await websocket.recv()
            print(f"Tools list response: {response}")
            
            # Test barcode generation
            barcode_message = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "barcode_generator",
                    "arguments": {
                        "data": "123456789",
                        "format": "code128",
                        "width": 200,
                        "height": 100
                    }
                }
            }
            
            await websocket.send(json.dumps(barcode_message))
            response = await websocket.recv()
            parsed_response = json.loads(response)
            print(f"Barcode generation response: {parsed_response['result']['content'][0]['type'] if 'result' in parsed_response else 'Error'}")
            
            print("WebSocket MCP test completed successfully!")
            
    except Exception as e:
        print(f"WebSocket test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_mcp())