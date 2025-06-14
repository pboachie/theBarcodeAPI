# app/api/websocket_mcp.py

import json
import logging
import uuid
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, status
from fastapi.websockets import WebSocketState
from app.config import settings
from app.redis_manager import RedisManager
from app.redis import get_redis_manager
from app.barcode_generator import BarcodeGenerator
from app.schemas import BarcodeRequest, MCPClientAuthResponse, MCPClientAuthRequest
from app.rate_limiter import rate_limit
from app.dependencies import get_client_ip

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

# Client authentication constants
CLIENT_ID_PREFIX = "mcp_client:"
CLIENT_ID_EXPIRY = 1800  # 30 minutes in seconds
AUTH_RATE_LIMIT_KEY = "mcp_auth_rate_limit:"
AUTH_RATE_LIMIT_INTERVAL = 1800  # 30 minutes in seconds

async def generate_client_id(redis_manager: RedisManager, client_ip: str) -> str:
    """
    Generate a unique client ID and store it in Redis with expiration.
    
    Args:
        redis_manager: Redis connection manager
        client_ip: Client IP address for rate limiting
        
    Returns:
        str: Generated client ID
        
    Raises:
        HTTPException: If rate limit is exceeded
    """
    # Check rate limit for this IP
    rate_limit_key = f"{AUTH_RATE_LIMIT_KEY}{client_ip}"
    
    # Check if this IP has generated a client ID recently
    existing_rate_limit = await redis_manager.redis.get(rate_limit_key)
    if existing_rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. You can only generate one client ID every 30 minutes."
        )
    
    # Generate unique client ID
    client_id = str(uuid.uuid4())
    
    # Store client ID in Redis with expiration
    client_key = f"{CLIENT_ID_PREFIX}{client_id}"
    await redis_manager.redis.setex(
        client_key, 
        CLIENT_ID_EXPIRY, 
        json.dumps({
            "created_at": int(time.time()),
            "client_ip": client_ip,
            "expires_at": int(time.time()) + CLIENT_ID_EXPIRY
        })
    )
    
    # Set rate limit for this IP
    await redis_manager.redis.setex(rate_limit_key, AUTH_RATE_LIMIT_INTERVAL, "1")
    
    logger.info(f"Generated client ID {client_id} for IP {client_ip}")
    return client_id

async def validate_client_id(redis_manager: RedisManager, client_id: str) -> bool:
    """
    Validate that a client ID exists and is not expired.
    
    Args:
        redis_manager: Redis connection manager
        client_id: Client ID to validate
        
    Returns:
        bool: True if client ID is valid, False otherwise
    """
    try:
        client_key = f"{CLIENT_ID_PREFIX}{client_id}"
        client_data = await redis_manager.redis.get(client_key)
        
        if not client_data:
            logger.warning(f"Client ID {client_id} not found")
            return False
            
        # Parse client data
        client_info = json.loads(client_data)
        current_time = int(time.time())
        
        # Check if expired
        if current_time > client_info.get("expires_at", 0):
            logger.warning(f"Client ID {client_id} has expired")
            # Clean up expired client ID
            await redis_manager.redis.delete(client_key)
            return False
            
        logger.debug(f"Client ID {client_id} is valid")
        return True
        
    except Exception as e:
        logger.error(f"Error validating client ID {client_id}: {e}")
        return False

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

@router.post("/auth", response_model=MCPClientAuthResponse, summary="Generate MCP WebSocket client ID")
@rate_limit(times=1, interval=30, period="minutes")
async def generate_mcp_client_id(
    request: Request,
    auth_request: MCPClientAuthRequest,
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    Generate a client ID for WebSocket MCP connection.
    
    **Rate Limited**: 1 request per 30 minutes per IP address.
    **Client ID Expiry**: 30 minutes after generation.
    
    Returns:
        MCPClientAuthResponse: Contains client_id, expiry info, and WebSocket URL
        
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    try:
        client_ip = await get_client_ip(request)
        client_id = await generate_client_id(redis_manager, client_ip)
        
        # Build WebSocket URL
        base_url = settings.SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")
        websocket_url = f"{base_url}/api/v1/mcp/ws/{client_id}"
        
        return MCPClientAuthResponse(
            client_id=client_id,
            expires_in=CLIENT_ID_EXPIRY,
            websocket_url=websocket_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating client ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate client ID"
        )

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    client_id: str,
    redis_manager: RedisManager = Depends(get_redis_manager)
):
    """
    WebSocket endpoint for MCP (Model Context Protocol) communication.
    
    **Authentication Required**: client_id must be obtained from `/api/v1/mcp/auth` endpoint first.
    
    This endpoint provides WebSocket support for AI assistants and other clients
    to interact with the Barcode API using the MCP protocol.
    
    Args:
        client_id: Valid client ID obtained from auth endpoint (expires in 30 minutes)
    """
    # Validate client ID before accepting connection
    if not await validate_client_id(redis_manager, client_id):
        logger.warning(f"WebSocket connection rejected for invalid client ID: {client_id}")
        await websocket.close(code=4003, reason="Invalid or expired client ID. Please obtain a new client ID from /api/v1/mcp/auth")
        return
    
    await ws_manager.connect(websocket, client_id)
    logger.info(f"Authenticated WebSocket connection established for client {client_id}")
    
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