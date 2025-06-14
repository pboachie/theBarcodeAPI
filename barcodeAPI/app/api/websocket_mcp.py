# app/api/websocket_mcp.py

import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState
from app.config import settings
from app.redis_manager import RedisManager
from app.redis import get_redis_manager
from app.barcode_generator import BarcodeGenerator
from app.schemas import BarcodeRequest

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/mcp",
    tags=["MCP WebSocket"],
)

class MCPWebSocketManager:
    """Manager for MCP (Model Context Protocol) WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_count = 0
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a WebSocket connection and add it to active connections."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_count += 1
        logger.info(f"WebSocket connection established for client {client_id}. Total connections: {self.connection_count}")
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.connection_count -= 1
            logger.info(f"WebSocket connection closed for client {client_id}. Total connections: {self.connection_count}")
    
    async def send_personal_message(self, message: str, client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        for client_id, websocket in self.active_connections.items():
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to client {client_id}: {e}")
                    self.disconnect(client_id)

# Global WebSocket manager instance
ws_manager = MCPWebSocketManager()

async def handle_mcp_message(message: Dict[str, Any], client_id: str, redis_manager: RedisManager) -> Dict[str, Any]:
    """
    Handle MCP protocol messages.
    
    Args:
        message: The incoming MCP message
        client_id: The client identifier
        redis_manager: Redis connection manager
        
    Returns:
        Dict containing the response message
    """
    try:
        method = message.get("method")
        params = message.get("params", {})
        message_id = message.get("id")
        
        if method == "initialize":
            return {
                "id": message_id,
                "result": {
                    "protocolVersion": "1.0.0",
                    "serverInfo": {
                        "name": "theBarcodeAPI AGSC Server",
                        "version": settings.API_VERSION
                    },
                    "capabilities": {
                        "tools": ["barcode_generator"],
                        "resources": ["health", "metrics"]
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "id": message_id,
                "result": {
                    "tools": [
                        {
                            "name": "barcode_generator",
                            "description": "Generate barcodes with various formats and parameters",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "data": {"type": "string", "description": "Data to encode"},
                                    "format": {"type": "string", "description": "Barcode format"},
                                    "width": {"type": "integer", "description": "Barcode width"},
                                    "height": {"type": "integer", "description": "Barcode height"}
                                },
                                "required": ["data", "format"]
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name == "barcode_generator":
                # Create barcode request
                barcode_request = BarcodeRequest(
                    data=tool_args.get("data", ""),
                    format=tool_args.get("format", "code128"),
                    width=tool_args.get("width", 200),
                    height=tool_args.get("height", 100)
                )
                
                # Generate barcode
                generator = BarcodeGenerator()
                barcode_data = generator.generate_barcode(barcode_request)
                
                return {
                    "id": message_id,
                    "result": {
                        "content": [
                            {
                                "type": "image",
                                "data": barcode_data["image_data"],
                                "mimeType": f"image/{barcode_data['format']}"
                            }
                        ]
                    }
                }
            else:
                return {
                    "id": message_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
        
        elif method == "resources/list":
            return {
                "id": message_id,
                "result": {
                    "resources": [
                        {
                            "uri": "health://status",
                            "name": "Health Status",
                            "description": "Current server health status"
                        },
                        {
                            "uri": "metrics://system",
                            "name": "System Metrics",
                            "description": "System performance metrics"
                        }
                    ]
                }
            }
        
        elif method == "resources/read":
            uri = params.get("uri")
            if uri == "health://status":
                # Get health status from Redis
                health_data = await redis_manager.redis.get("detailed_health_check")
                if health_data:
                    health_info = json.loads(health_data)
                else:
                    health_info = {"status": "unknown", "message": "Health data not available"}
                
                return {
                    "id": message_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(health_info, indent=2)
                            }
                        ]
                    }
                }
            else:
                return {
                    "id": message_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown resource: {uri}"
                    }
                }
        
        else:
            return {
                "id": message_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                }
            }
    
    except Exception as e:
        logger.error(f"Error handling MCP message: {e}", exc_info=True)
        return {
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    client_id: str,
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    WebSocket endpoint for MCP (Model Context Protocol) communication.
    
    This endpoint provides WebSocket support for AI assistants and other clients
    to interact with the Barcode API using the MCP protocol.
    """
    await ws_manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                logger.debug(f"Received MCP message from {client_id}: {message}")
                
                # Handle the MCP message
                response = await handle_mcp_message(message, client_id, redis_manager)
                
                # Send response back to client
                await ws_manager.send_personal_message(json.dumps(response), client_id)
                logger.debug(f"Sent MCP response to {client_id}: {response}")
                
            except json.JSONDecodeError:
                error_response = {
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Invalid JSON"
                    }
                }
                await ws_manager.send_personal_message(json.dumps(error_response), client_id)
                
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        ws_manager.disconnect(client_id)

@router.get("/status")
async def get_websocket_status():
    """Get current WebSocket connection status."""
    return {
        "status": "ok",
        "active_connections": ws_manager.connection_count,
        "server_info": {
            "name": "theBarcodeAPI AGSC Server",
            "version": settings.API_VERSION,
            "protocol": "MCP 1.0.0"
        }
    }