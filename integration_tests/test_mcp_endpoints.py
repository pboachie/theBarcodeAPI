import httpx
import asyncio
import json
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"
SSE_URL = f"{BASE_URL}/api/mcp/sse"
CMD_URL = f"{BASE_URL}/api/mcp/cmd"

def print_step(message):
    print(f"\n[STEP] {message}")

def print_assertion(message, success):
    status = "SUCCESS" if success else "FAILURE"
    print(f"[ASSERTION] {message}: {status}")
    if not success:
        sys.exit(f"Assertion failed: {message}")

async def get_client_id_from_sse(client: httpx.AsyncClient, sse_response: httpx.Response) -> str:
    """Helper to get client_id from SSE stream."""
    client_id = None
    async for event in sse_response.aiter_sse():
        print(f"SSE Event: type={event.event}, data={event.data}, id={event.id}")
        if event.event == "client_id":
            client_id = event.data # data is the client_id string
            print_step(f"Received client_id: {client_id}")
            break
        elif event.event == "error": # Handle server config error during SSE setup
            print_assertion(f"SSE connection failed with server error: {event.data}", False)
            
    if client_id is None:
        print_assertion("Failed to receive client_id from SSE stream.", False)
    return client_id

async def scenario_1_successful_barcode_generation():
    print_step("Starting Scenario 1: Successful Barcode Generation")
    async with httpx.AsyncClient(timeout=30.0) as client: # Increased timeout for full scenario
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_URL}")
            async with client.stream("GET", SSE_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)
                
                client_id = await get_client_id_from_sse(client, sse_response)

                print_step(f"Sending POST request to CMD endpoint: {CMD_URL}")
                request_id = str(uuid.uuid4())
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "generate_barcode_mcp",
                    "params": {
                        "data": "123456789012", # EAN13 needs 12 or 13 digits
                        "format": "EAN13",
                        "image_format": "PNG",
                        "show_text": True
                    },
                    "id": request_id
                }
                headers = {"X-Client-ID": client_id, "Content-Type": "application/json"}
                
                cmd_response = await client.post(CMD_URL, json=mcp_request, headers=headers)
                print_assertion(f"CMD endpoint response status is 202", cmd_response.status_code == 202)
                if cmd_response.status_code != 202:
                    print(f"CMD Response: {cmd_response.text}")


                print_step("Listening on SSE stream for JSON-RPC response...")
                mcp_response_received = False
                async for event in sse_response.aiter_sse():
                    print(f"SSE Event: type={event.event}, data={event.data}")
                    if event.event == "mcp_response":
                        try:
                            response_data = json.loads(event.data)
                            print_assertion("MCP response 'id' matches request 'id'", response_data.get("id") == request_id)
                            print_assertion("MCP response contains 'result'", "result" in response_data)
                            if "result" in response_data:
                                result_value = response_data["result"]
                                print_assertion("Result is a string", isinstance(result_value, str))
                                print_assertion("Result starts with 'data:image/png;base64,'", result_value.startswith("data:image/png;base64,"))
                                print(f"Received base64 image string (first 50 chars): {result_value[:50]}...")
                            mcp_response_received = True
                            break 
                        except json.JSONDecodeError:
                            print_assertion("Failed to decode JSON from mcp_response data", False)
                        except Exception as e:
                            print_assertion(f"Error processing mcp_response: {e}", False)
                
                print_assertion("MCP response was received via SSE", mcp_response_received)
                print_step("Closing SSE connection for Scenario 1.")
            # SSE connection closed automatically here
        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in Scenario 1: {e}", False)

async def scenario_2_client_disconnects():
    print_step("Starting Scenario 2: Client Disconnects from SSE then tries CMD")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_URL} to get client_id")
            client_id = None
            async with client.stream("GET", SSE_URL) as sse_response:
                if sse_response.status_code != 200:
                     raw_content = await sse_response.aread()
                     print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)
                client_id = await get_client_id_from_sse(client, sse_response)
            print_step(f"SSE connection closed after getting client_id: {client_id}")

            print_assertion("Client ID was obtained", client_id is not None)

            print_step(f"Sending POST request to CMD endpoint with stale client_id: {CMD_URL}")
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "generate_barcode_mcp", # Method doesn't matter much here
                "params": {"data": "test", "format": "QR"},
                "id": str(uuid.uuid4())
            }
            headers = {"X-Client-ID": client_id, "Content-Type": "application/json"}
            
            cmd_response = await client.post(CMD_URL, json=mcp_request, headers=headers)
            print_assertion(f"CMD endpoint response status is 404 (Client not connected)", cmd_response.status_code == 404)
            if cmd_response.status_code != 404:
                 print(f"CMD Response: {cmd_response.text}")

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in Scenario 2: {e}", False)

async def scenario_3_invalid_mcp_command():
    print_step("Starting Scenario 3: Invalid MCP Command (Method not found)")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_URL}")
            async with client.stream("GET", SSE_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)

                client_id = await get_client_id_from_sse(client, sse_response)

                print_step(f"Sending POST request to CMD endpoint for an unknown_method: {CMD_URL}")
                request_id = str(uuid.uuid4())
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "unknown_method_12345",
                    "params": {},
                    "id": request_id
                }
                headers = {"X-Client-ID": client_id, "Content-Type": "application/json"}
                
                cmd_response = await client.post(CMD_URL, json=mcp_request, headers=headers)
                print_assertion(f"CMD endpoint response status is 202", cmd_response.status_code == 202)
                if cmd_response.status_code != 202:
                    print(f"CMD Response: {cmd_response.text}")

                print_step("Listening on SSE stream for JSON-RPC error response...")
                error_response_received = False
                async for event in sse_response.aiter_sse():
                    print(f"SSE Event: type={event.event}, data={event.data}")
                    if event.event == "mcp_response":
                        try:
                            response_data = json.loads(event.data)
                            print_assertion("Error response 'id' matches request 'id'", response_data.get("id") == request_id)
                            print_assertion("Error response contains 'error' object", "error" in response_data)
                            if "error" in response_data:
                                error_obj = response_data["error"]
                                print_assertion("Error code is -32601 (Method not found)", error_obj.get("code") == -32601)
                                print(f"Received error: code={error_obj.get('code')}, message='{error_obj.get('message')}'")
                            error_response_received = True
                            break
                        except json.JSONDecodeError:
                            print_assertion("Failed to decode JSON from mcp_response data for error", False)
                        except Exception as e:
                            print_assertion(f"Error processing mcp_response for error: {e}", False)
                
                print_assertion("MCP error response was received via SSE", error_response_received)
                print_step("Closing SSE connection for Scenario 3.")
            # SSE connection closed automatically here
        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in Scenario 3: {e}", False)

async def main():
    print_step("Starting MCP Endpoint Integration Tests")
    
    await scenario_1_successful_barcode_generation()
    await scenario_2_client_disconnects()
    await scenario_3_invalid_mcp_command()
    
    print("\n[INFO] All scenarios completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("[INFO] Integration tests passed successfully.")
    except Exception as e: # Should not happen if print_assertion exits
        print(f"[FATAL_ERROR] An unexpected error occurred at the top level: {e}")
        sys.exit(1)
```
