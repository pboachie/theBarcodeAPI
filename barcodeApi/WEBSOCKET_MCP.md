# WebSocket MCP Support for theBarcodeAPI

## Overview

The Barcode API now includes WebSocket support for MCP (Model Context Protocol) communication, providing an AGSC (AI/Assistant Generation Service Compatible) server that works seamlessly in Docker environments.

## Features

- **WebSocket Endpoints**: Real-time communication support
- **MCP Protocol Compliance**: Full Model Context Protocol v1.0.0 support
- **Docker Integration**: Optimized for containerized deployments
- **AGSC Server**: AI/Assistant compatible server functionality

## WebSocket Endpoints

### Connection
- **URL**: `ws://your-domain:8000/api/v1/mcp/ws/{client_id}`
- **Protocol**: WebSocket with JSON-RPC 2.0 messages

### Status Check
- **URL**: `GET /api/v1/mcp/status`
- **Response**: Current WebSocket server status and connection count

## MCP Protocol Support

### Supported Methods

1. **initialize**: Initialize MCP session
2. **tools/list**: List available tools
3. **tools/call**: Execute barcode generation tool
4. **resources/list**: List available resources
5. **resources/read**: Read health and metrics data

### Example Usage

```javascript
// Initialize connection
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "1.0.0",
    "clientInfo": {
      "name": "my-client",
      "version": "1.0.0"
    }
  }
}

// Generate barcode
{
  "jsonrpc": "2.0",
  "id": 2,
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
```

## Docker Configuration

The WebSocket functionality is automatically available when running the Docker container. The health check now includes WebSocket endpoint verification.

### Environment Variables

All existing environment variables are supported. No additional configuration needed for WebSocket functionality.

### Health Checks

The Docker health check now verifies both HTTP and WebSocket endpoints:
- HTTP: `curl -f http://localhost:8000/health`
- WebSocket: `python3 check_websocket_health.py`

## Testing

Use the provided test script:

```bash
cd barcodeAPI
python3 tests/test_websocket_mcp.py
```

## Integration

The WebSocket MCP server integrates seamlessly with:
- Existing barcode generation functionality
- Redis caching and rate limiting
- Database operations
- Health monitoring systems

## Security

- CORS support for WebSocket connections
- Same authentication and rate limiting as HTTP endpoints
- Secure WebSocket connections (WSS) supported in production