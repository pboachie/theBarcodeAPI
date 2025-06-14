# Remote Connections Guide 🚀

Welcome to the comprehensive guide for connecting to theBarcodeAPI's WebSocket MCP endpoint! This guide will help you test the MCP functionality before integrating it with AI agents or other applications.

## 🎯 Quick Start: Test the MCP Endpoint

### The Magic URL
```
ws://your-domain:8000/api/v1/mcp/ws/test-client
```

For local testing:
```
ws://localhost:8000/api/v1/mcp/ws/test-client
```

## 🛠️ Testing Methods

### Method 1: Browser Developer Console (Easiest!)

1. **Open your browser** and navigate to any page
2. **Open Developer Tools** (F12)
3. **Go to Console tab**
4. **Copy and paste this code:**

```javascript
// 🔌 Connect to the WebSocket MCP endpoint
console.log('🚀 Connecting to Barcode API WebSocket...');
const ws = new WebSocket('ws://localhost:8000/api/v1/mcp/ws/test-client');

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
🔍 MCP WebSocket Connection Tester
Perfect for testing before AI agent integration!
"""

import asyncio
import websockets
import json
import time

async def test_mcp_connection():
    """Test the MCP WebSocket endpoint with various scenarios."""
    
    uri = "ws://localhost:8000/api/v1/mcp/ws/test-client"
    
    print("🚀 Starting MCP WebSocket Connection Test...")
    print(f"📡 Connecting to: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
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

Install websocat first:
```bash
# On macOS
brew install websocat

# On Ubuntu/Debian
sudo apt install websocat

# Or download from: https://github.com/vi/websocat
```

Then test:
```bash
# Connect and send initialize message
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"1.0.0","clientInfo":{"name":"curl-test","version":"1.0.0"}}}' | websocat ws://localhost:8000/api/v1/mcp/ws/test-client
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

- [ ] ✅ Can connect to `ws://localhost:8000/api/v1/mcp/ws/test-client`
- [ ] ✅ Initialize method works and returns server info
- [ ] ✅ Tools/list shows available barcode generation tools
- [ ] ✅ Can generate Code128 barcodes
- [ ] ✅ Can generate QR codes
- [ ] ✅ Base64 images are returned correctly
- [ ] ✅ Error handling works for invalid requests
- [ ] ✅ Connection stays stable during multiple requests

## 🌟 Pro Tips

1. **Use unique client IDs** for different test sessions: `test-client-1`, `test-client-2`, etc.
2. **Test error scenarios** by sending invalid JSON or missing parameters
3. **Monitor connection count** via `/api/v1/mcp/status` endpoint
4. **Test with different data sizes** - try short and long barcode data
5. **Simulate real AI assistant behavior** with proper initialization and tool discovery

## 🔗 Ready for AI Agents!

Once you've successfully tested with `test-client`, your AI agents can connect using:
- **Claude MCP**: Use the WebSocket URL in your MCP configuration
- **GPT Actions**: Configure as a WebSocket action endpoint  
- **Custom Agents**: Use any WebSocket client library

---

**Happy Testing! 🚀**

Got questions? The WebSocket MCP endpoint is production-ready and waiting for your AI agents to discover the power of real-time barcode generation!