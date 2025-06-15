# Remote Connections Guide 🚀

Welcome to the comprehensive guide for connecting to theBarcodeAPI's **authenticated** WebSocket MCP endpoint! This guide will help you test the MCP functionality before integrating it with AI agents or other applications.

## 🔐 Authentication Required

**IMPORTANT**: As of the latest update, all WebSocket connections require authentication. You must first obtain a client ID before connecting.

## 🎯 Quick Start: 3-Step Process

### Step 1: Get a Client ID
**Rate Limited**: 1 request per 30 minutes per IP address.

```bash
# Request authentication (replace with your server URL)
curl -X POST "http://localhost:8000/api/v1/mcp/auth" \
     -H "Content-Type: application/json" \
     -d "{}"
```

**Response Example:**
```json
{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_in": 1800,
  "websocket_url": "ws://localhost:8000/api/v1/mcp/ws/550e8400-e29b-41d4-a716-446655440000"
}
```

### Step 2: Use the WebSocket URL
```
ws://localhost:8000/api/v1/mcp/ws/550e8400-e29b-41d4-a716-446655440000
```

### Step 3: Connect and Test
Now you can connect using any of the methods below!

## 🛠️ Testing Methods

### Method 1: Browser Developer Console (Easiest!)

**Prerequisites**: First get a client ID using the curl command above, then use the returned `websocket_url`.

1. **Open your browser** and navigate to any page
2. **Open Developer Tools** (F12)
3. **Go to Console tab**
4. **Copy and paste this code** (replace the URL with your actual websocket_url):

```javascript
// 🔌 Connect to the WebSocket MCP endpoint with authentication
console.log('🚀 Connecting to Barcode API WebSocket...');
// REPLACE THIS URL with your actual websocket_url from the auth response
const ws = new WebSocket('ws://localhost:8000/api/v1/mcp/ws/550e8400-e29b-41d4-a716-446655440000');

// 📡 Set up event handlers
ws.onopen = function() {
    console.log('✅ Connected! Initializing MCP session...');
    
    // Initialize the MCP session
    ws.send(JSON.stringify({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "1.0.0",
            "clientInfo": {
                "name": "browser-test-client",
                "version": "1.0.0"
            }
        }
    }));
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log('📨 Response received:', response);
    
    // If initialization successful, let's try generating a barcode!
    if (response.id === 1 && response.result) {
        console.log('🎉 MCP session initialized! Generating test barcode...');
        
        ws.send(JSON.stringify({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "barcode_generator",
                "arguments": {
                    "data": "WEBSOCKET-TEST-" + Date.now(),
                    "format": "code128",
                    "width": 400,
                    "height": 200
                }
            }
        }));
    }
};

ws.onerror = function(error) {
    console.error('❌ WebSocket error:', error);
};

ws.onclose = function() {
    console.log('🔌 Connection closed');
};

// Helper function to generate custom barcodes
window.generateBarcode = function(data, format = 'code128') {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            "jsonrpc": "2.0",
            "id": Date.now(),
            "method": "tools/call",
            "params": {
                "name": "barcode_generator",
                "arguments": {
                    "data": data,
                    "format": format,
                    "width": 300,
                    "height": 150
                }
            }
        }));
        console.log(`🎯 Generating ${format} barcode for: ${data}`);
    } else {
        console.log('❌ WebSocket not connected');
    }
};

console.log('💡 Tip: Use generateBarcode("your-data", "qr") to generate custom barcodes!');
```

5. **Watch the magic happen!** You should see connection logs and a test barcode generation.

### Method 2: Python Script (For Developers)

Create a file called `test_mcp_connection.py`:

```python
#!/usr/bin/env python3
"""
🔍 MCP WebSocket Connection Tester with Authentication
Perfect for testing before AI agent integration!
"""

import asyncio
import websockets
import json
import time
import requests

async def get_client_id():
    """Get authenticated client ID from the API."""
    print("🔐 Requesting client ID authentication...")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/mcp/auth",
            headers={"Content-Type": "application/json"},
            json={}
        )
        
        if response.status_code == 200:
            auth_data = response.json()
            print(f"✅ Authentication successful!")
            print(f"📋 Client ID: {auth_data['client_id']}")
            print(f"⏰ Expires in: {auth_data['expires_in']} seconds")
            return auth_data['websocket_url']
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        return None

async def test_mcp_connection():
    """Test the MCP WebSocket endpoint with authentication."""
    
    # Step 1: Get authenticated WebSocket URL
    websocket_url = await get_client_id()
    if not websocket_url:
        print("🚫 Cannot proceed without authentication")
        return
    
    print(f"🚀 Starting MCP WebSocket Connection Test...")
    print(f"📡 Connecting to: {websocket_url}")
    
    try:
        async with websockets.connect(websocket_url) as websocket:
            print("✅ Connected successfully!")
            
            # Test 1: Initialize MCP session
            print("\n🔧 Test 1: Initializing MCP session...")
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.0.0",
                    "clientInfo": {
                        "name": "python-test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            await websocket.send(json.dumps(init_message))
            response = await websocket.recv()
            print(f"📨 Initialize response: {json.loads(response)}")
            
            # Test 2: List available tools
            print("\n🛠️  Test 2: Listing available tools...")
            tools_message = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            await websocket.send(json.dumps(tools_message))
            response = await websocket.recv()
            print(f"📨 Tools list: {json.loads(response)}")
            
            # Test 3: Generate different barcode formats
            barcode_tests = [
                ("CODE128-DEMO", "code128"),
                ("QR-CODE-TEST", "qr"),
                ("123456789012", "ean13"),
                ("DATAMATRIX", "datamatrix")
            ]
            
            for i, (data, format_type) in enumerate(barcode_tests, 3):
                print(f"\n🎯 Test {i}: Generating {format_type.upper()} barcode...")
                barcode_message = {
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": "tools/call",
                    "params": {
                        "name": "barcode_generator",
                        "arguments": {
                            "data": data,
                            "format": format_type,
                            "width": 300,
                            "height": 200
                        }
                    }
                }
                
                await websocket.send(json.dumps(barcode_message))
                response = await websocket.recv()
                result = json.loads(response)
                
                if "result" in result and "base64_image" in result["result"]:
                    print(f"✅ {format_type.upper()} barcode generated successfully!")
                    print(f"🖼️  Image size: ~{len(result['result']['base64_image'])} characters (base64)")
                else:
                    print(f"❌ Failed to generate {format_type} barcode: {result}")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
            
            print("\n🎉 All tests completed successfully!")
            print("💡 Your MCP endpoint is ready for AI agent integration!")
            
    except websockets.exceptions.ConnectionRefused:
        print("❌ Connection refused. Make sure the Barcode API server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
```

Run it with:
```bash
python3 test_mcp_connection.py
```

### Method 3: cURL + websocat (Command Line Heroes)

**Step 1**: Get a client ID first:
```bash
# Get authenticated client ID
CLIENT_AUTH=$(curl -X POST "http://localhost:8000/api/v1/mcp/auth" -H "Content-Type: application/json" -d "{}")
echo "Auth Response: $CLIENT_AUTH"

# Extract the websocket URL (you'll need to copy this manually)
```

**Step 2**: Install websocat:
```bash
# On macOS
brew install websocat

# On Ubuntu/Debian
sudo apt install websocat

# Or download from: https://github.com/vi/websocat
```

**Step 3**: Connect with the authenticated URL:
```bash
# Replace with your actual websocket URL from Step 1
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"1.0.0","clientInfo":{"name":"curl-test","version":"1.0.0"}}}' | websocat ws://localhost:8000/api/v1/mcp/ws/YOUR-CLIENT-ID-HERE
```

## 🎨 Creative Testing Scenarios

### Scenario 1: "The AI Assistant Simulator"
Test like an AI assistant would connect:

```javascript
const aiAssistantTest = {
    clientInfo: {
        name: "ClaudeAI-Simulator",
        version: "3.0.0",
        capabilities: ["barcode-generation", "real-time-processing"]
    }
};

// Use this in your initialize params
```

### Scenario 2: "The Batch Barcode Generator"
Test multiple barcode generation:

```python
async def batch_test():
    # Connect to ws://localhost:8000/api/v1/mcp/ws/batch-test-client
    
    batch_data = [
        "PRODUCT-001", "PRODUCT-002", "PRODUCT-003",
        "SKU-ABC123", "SKU-DEF456", "SKU-GHI789"
    ]
    
    for item in batch_data:
        # Generate barcode for each item
        # ... (send barcode generation message)
```

### Scenario 3: "The Format Explorer"
Test all supported formats:

```javascript
const formats = ['code128', 'qr', 'ean13', 'ean8', 'upca', 'upce', 'datamatrix'];
formats.forEach(format => {
    generateBarcode(`TEST-${format.toUpperCase()}`, format);
});
```

### Method 4: HTTP MCP Endpoints (RESTful Testing)

**New Feature**: FastMCP-compliant HTTP endpoints for clients that prefer REST over WebSocket!

These endpoints don't require client authentication and can be tested immediately:

#### Initialize Session
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/initialize" \
     -H "Content-Type: application/json" \
     -d '{
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
     }'
```

#### List Available Tools
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/tools/list" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 2,
       "method": "tools/list",
       "params": {}
     }'
```

#### Generate a Barcode
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/tools/call" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 3,
       "method": "tools/call",
       "params": {
         "name": "barcode_generator",
         "arguments": {
           "data": "Hello World",
           "format": "code128",
           "width": 300,
           "height": 100
         }
       }
     }'
```

#### List Available Resources
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/resources/list" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 4,
       "method": "resources/list",
       "params": {}
     }'
```

#### Read Resource Data
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/resources/read" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 5,
       "method": "resources/read",
       "params": {
         "uri": "health://status"
       }
     }'
```

### Method 5: Server-Sent Events (SSE) Legacy Support

**New Feature**: SSE endpoint for clients that need real-time updates but can't use WebSocket!

**Note**: SSE endpoint requires client authentication (same as WebSocket).

#### Step 1: Get Client ID (same as WebSocket)
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/auth" \
     -H "Content-Type: application/json" \
     -d "{}"
```

#### Step 2: Connect to SSE Endpoint
```bash
# Replace client_id with your actual client ID
curl -N -H "Accept: text/event-stream" \
     "http://localhost:8000/api/v1/mcp/sse/YOUR_CLIENT_ID_HERE"
```

#### Example SSE Output:
```
data: {"type": "connected", "client_id": "550e8400-e29b-41d4-a716-446655440000", "timestamp": 1703174400}

data: {"type": "heartbeat", "timestamp": 1703174430, "active_connections": 1}

data: {"type": "heartbeat", "timestamp": 1703174460, "active_connections": 1}
```

### Method 6: JavaScript Event Source (Browser SSE)

```javascript
// First get a client ID (use Method 1 auth approach)
const clientId = "YOUR_CLIENT_ID_HERE"; // Replace with actual client ID

// Connect to SSE endpoint
const eventSource = new EventSource(`http://localhost:8000/api/v1/mcp/sse/${clientId}`);

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('📡 SSE Event:', data);
    
    switch(data.type) {
        case 'connected':
            console.log('✅ Connected to SSE endpoint');
            break;
        case 'heartbeat':
            console.log(`💓 Heartbeat - Active connections: ${data.active_connections}`);
            break;
        case 'error':
            console.log('❌ Error:', data.message);
            break;
    }
};

eventSource.onerror = function(event) {
    console.log('❌ SSE Error:', event);
};

// Clean up
// eventSource.close();
```

## 📊 Connection Method Comparison

| Method | Auth Required | Real-time | Complexity | Best For |
|--------|---------------|-----------|------------|----------|
| **WebSocket** | ✅ Yes | ✅ Yes | Medium | AI agents, real-time apps |
| **HTTP MCP** | ❌ No | ❌ No | Low | Simple testing, REST clients |
| **SSE** | ✅ Yes | ✅ Partial | Medium | Legacy browsers, monitoring |

## 🔄 Connection Preferences

**For Testing (Recommended Order):**
1. **HTTP MCP** - Quick testing without auth
2. **WebSocket** - Full-featured, authenticated testing
3. **SSE** - Legacy/monitoring testing

**For Production:**
- **AI Assistants**: WebSocket (authenticated, real-time)
- **Web Apps**: WebSocket or SSE (depending on interactivity needs)
- **Backend Services**: HTTP MCP (simple request-response)

## 🚨 Common Issues & Solutions

### Issue: "Connection Refused"
**Solution:** Make sure the Docker container is running:
```bash
cd barcodeAPI
docker-compose up --build
```

### Issue: "WebSocket Upgrade Failed"
**Solution:** Check if you're using the correct protocol (ws:// not http://)

### Issue: "Invalid JSON-RPC message"
**Solution:** Ensure your JSON is properly formatted with required fields:
- `jsonrpc: "2.0"`
- `id: <number>`
- `method: <string>`

## 🧪 Integration Testing Checklist

Before giving the endpoint to your AI agent, verify:

**Authentication & Connection:**
- [ ] ✅ Can get client ID from `/api/v1/mcp/auth` endpoint
- [ ] ✅ Client ID is valid (UUID format)
- [ ] ✅ WebSocket URL is correctly formatted
- [ ] ✅ Can connect to authenticated WebSocket URL
- [ ] ✅ Connection rejects invalid/expired client IDs
- [ ] ✅ SSE endpoint works with valid client ID
- [ ] ✅ SSE endpoint rejects invalid client IDs

**HTTP MCP Protocol (No Auth Required):**
- [ ] ✅ `/api/v1/mcp/initialize` returns server info
- [ ] ✅ `/api/v1/mcp/tools/list` shows barcode generator tool
- [ ] ✅ `/api/v1/mcp/tools/call` generates barcodes successfully
- [ ] ✅ `/api/v1/mcp/resources/list` shows available resources
- [ ] ✅ `/api/v1/mcp/resources/read` returns health status

**WebSocket MCP Protocol (Auth Required):**
- [ ] ✅ Initialize method works and returns server info
- [ ] ✅ Tools/list shows available barcode generation tools
- [ ] ✅ Can generate Code128 barcodes
- [ ] ✅ Can generate QR codes
- [ ] ✅ Base64 images are returned correctly
- [ ] ✅ Error handling works for invalid requests
- [ ] ✅ Connection stays stable during multiple requests

**SSE Protocol (Auth Required):**
- [ ] ✅ SSE connection establishes successfully
- [ ] ✅ Receives connection confirmation event
- [ ] ✅ Receives periodic heartbeat events
- [ ] ✅ Connection metrics are updated correctly

**Rate Limiting & Security:**
- [ ] ✅ Auth endpoint respects 30-minute rate limit
- [ ] ✅ Client IDs expire after 30 minutes
- [ ] ✅ Cannot reuse expired client IDs
- [ ] ✅ HTTP MCP endpoints work without authentication
- [ ] ✅ WebSocket/SSE endpoints require valid client IDs

## 🌟 Pro Tips

1. **Get fresh client IDs** - Remember they expire in 30 minutes!
2. **Handle rate limits** - You can only get 1 client ID per 30 minutes per IP
3. **Test error scenarios** by sending invalid JSON or missing parameters
4. **Monitor connection count** via `/api/v1/mcp/status` endpoint
5. **Test with different data sizes** - try short and long barcode data
6. **Simulate real AI assistant behavior** with proper initialization and tool discovery
7. **Plan ahead** - Get your client ID before starting your AI agent session

## 🔗 Ready for AI Agents!

Once you've successfully tested with authenticated connections, your AI agents can connect using:
- **Claude MCP**: Use the authenticated WebSocket URL in your MCP configuration
- **GPT Actions**: Configure as a WebSocket action endpoint with pre-auth step
- **Custom Agents**: Use any WebSocket client library with the 2-step auth process

---

**Happy Testing! 🚀**

Got questions? The WebSocket MCP endpoint is production-ready and waiting for your AI agents to discover the power of real-time barcode generation!