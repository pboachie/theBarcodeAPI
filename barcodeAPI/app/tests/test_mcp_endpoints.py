import httpx
import asyncio
import json
import uuid
import sys
from typing import Optional # Added Optional

BASE_URL = "http://127.0.0.1:8000"
SSE_URL = f"{BASE_URL}/api/v1/mcp/sse"

def print_step(message):
    print(f"\n[STEP] {message}")

def print_assertion(message, success):
    status = "SUCCESS" if success else "FAILURE"
    print(f"[ASSERTION] {message}: {status}")
    if not success:
        sys.exit(f"Assertion failed: {message}")

async def get_client_id_from_sse(client: httpx.AsyncClient, sse_response: httpx.Response) -> Optional[str]: # Changed to Optional[str]
    """Helper to get client_id from SSE stream."""
    client_id: Optional[str] = None # Ensure client_id is Optional
    async for event in sse_response.aiter_sse():
        print(f"SSE Event: type={event.event}, data={event.data}, id={event.id}")
        if event.event == "client_id":
            client_id = event.data # data is the client_id string
            print_step(f"Received client_id: {client_id}")
            break
        elif event.event == "error": # Handle server config error during SSE setup
            print_assertion(f"SSE connection failed with server error: {event.data}", False)
            return None # Explicitly return None on error

    if client_id is None:
        print_assertion("Failed to receive client_id from SSE stream.", False)
        # The above print_assertion will sys.exit, so this path might not be hit often in practice,
        # but it's good for type safety to ensure None is returned if loop finishes without client_id.
        return None
    return client_id

async def send_mcp_request_via_sse(client: httpx.AsyncClient, client_id: Optional[str], method: str, params: dict, request_id: str):
    """Helper to send MCP request via SSE (simulated by POSTing to a conceptual MCP processing endpoint).
       In a real FastMCP setup, the client would send JSON-RPC directly over the established SSE connection's
       associated POST endpoint or another mechanism defined by FastMCP for sending commands.
       For this test, we'll assume a hypothetical endpoint or mechanism that FastMCP uses internally
       or that the main app exposes to trigger processing for an SSE client.
       This will likely need to be adjusted based on how FastMCP expects commands for SSE clients.
       A common pattern is a general /mcp endpoint that takes client_id in headers.
       Let's assume for now the application's main FastMCP router handles this.
       We will use the SSE_URL for POSTing commands as per FastMCP typical behavior.
    """
    mcp_request_payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    # FastMCP typically uses the same SSE endpoint for POSTing commands,
    # identifying the client via a session or a specific header if required by the setup.
    # The X-Client-ID header was for the legacy /cmd endpoint. FastMCP manages client identity internally.
    headers = {"Content-Type": "application/json"}
    # If FastMCP requires a specific header for client identification when POSTing to the SSE URL, add it here.
    # For now, assuming FastMCP uses session state tied to the connection.
    print_step(f"Sending MCP request for client {client_id} to {SSE_URL}: {mcp_request_payload}")
    response = await client.post(SSE_URL, json=mcp_request_payload, headers=headers)
    # FastMCP's POST to SSE URL usually returns 200 OK with empty body or an immediate JSON-RPC error if the request is malformed.
    # The actual response to the MCP command comes asynchronously over the SSE stream.
    print_assertion(f"MCP request POST to {SSE_URL} status is 200 or similar success", response.status_code in [200, 202, 204])
    if response.status_code not in [200, 202, 204]:
        print(f"MCP Request POST Response: {response.text}")
    return response


async def scenario_1_successful_barcode_generation():
    print_step("Starting Scenario 1: Successful Barcode Generation via SSE")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_URL}")
            async with client.stream("GET", SSE_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)

                client_id = await get_client_id_from_sse(client, sse_response)
                if client_id is None: # Handle None case
                    print_assertion("Failed to get client_id for scenario 1", False)
                    return # Exit if no client_id

                request_id = str(uuid.uuid4())
                method = "generate_barcode_mcp"
                params = {
                    "data": "123456789012",
                    "format": "EAN13",
                    "image_format": "PNG",
                    "show_text": True
                }

                # Send MCP request (this might need adjustment based on FastMCP's actual command mechanism)
                # This simulates the client sending a JSON-RPC message *after* SSE is established.
                # FastMCP might expect this POST to the same SSE URL or a different one.
                # For now, we assume POSTing to SSE_URL itself.
                await send_mcp_request_via_sse(client, client_id, method, params, request_id)

                print_step("Listening on SSE stream for JSON-RPC response...")
                mcp_response_received = False
                async for event in sse_response.aiter_sse():
                    print(f"SSE Event: type={event.event}, data={event.data}")
                    if event.event == "mcp_response": # FastMCP might use a different event name or just send raw JSON
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
        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in Scenario 1: {e}", False)

async def scenario_2_client_disconnects_then_tries_command():
    print_step("Starting Scenario 2: Client Disconnects, then tries command (should fail)")
    async with httpx.AsyncClient(timeout=10.0) as client:
        original_client_id: Optional[str] = None # Ensure original_client_id is Optional
        try:
            # 1. Connect and get a client_id
            print_step(f"Connecting to SSE endpoint: {SSE_URL} to get client_id")
            async with client.stream("GET", SSE_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)
                original_client_id = await get_client_id_from_sse(client, sse_response)
            print_step(f"SSE connection closed after getting client_id: {original_client_id}")
            print_assertion("Client ID was obtained", original_client_id is not None)

            # 2. Try to send a command using the now-disconnected client_id.
            # FastMCP should reject this as the SSE connection associated with original_client_id is gone.
            # How FastMCP handles this (e.g. specific error code on POST, or no response) needs to be tested.
            # We'll assume POSTing to SSE_URL with an invalid/stale client_id (if it were passed in a header)
            # or just POSTing when no active session for that command exists would fail.
            print_step(f"Attempting to send MCP request with stale/disconnected client context to {SSE_URL}")
            request_id = str(uuid.uuid4())
            # We are not passing client_id explicitly in headers to send_mcp_request_via_sse
            # as FastMCP usually relies on the active connection.
            # The failure here would be that the server has no active connection to route this request to.
            cmd_response = await client.post(SSE_URL, json={
                "jsonrpc": "2.0", "method": "generate_barcode_mcp", "params": {}, "id": request_id
            }, headers={"Content-Type": "application/json"})

            # Expecting an error because there's no active SSE session for the server to associate this POST with.
            # FastMCP might return 400, 403, 404, or a JSON-RPC error if the POST is to the SSE endpoint.
            # This assertion may need adjustment based on actual FastMCP behavior for unassociated requests.
            print_assertion(f"Command POST to {SSE_URL} for disconnected client should fail (e.g., 400/403/404 or JSON RPC error)", cmd_response.status_code >= 400)
            if cmd_response.status_code < 400:
                print(f"Unexpected success on command POST: {cmd_response.text}")
            else:
                print(f"Received expected error status {cmd_response.status_code}: {cmd_response.text}")


        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in Scenario 2: {e}", False)


async def scenario_3_invalid_mcp_command():
    print_step("Starting Scenario 3: Invalid MCP Command (Method not found) via SSE")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_URL}")
            async with client.stream("GET", SSE_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)

                client_id = await get_client_id_from_sse(client, sse_response)
                if client_id is None: # Handle None case
                    print_assertion("Failed to get client_id for scenario 3", False)
                    return # Exit if no client_id
                request_id = str(uuid.uuid4())

                await send_mcp_request_via_sse(client, client_id, "unknown_method_12345", {}, request_id)

                print_step("Listening on SSE stream for JSON-RPC error response...")
                error_response_received = False
                async for event in sse_response.aiter_sse():
                    print(f"SSE Event: type={event.event}, data={event.data}")
                    if event.event == "mcp_response": # Or raw JSON
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
        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in Scenario 3: {e}", False)

async def main():
    print_step("Starting MCP Endpoint Integration Tests (FastMCP via SSE)")

    await scenario_1_successful_barcode_generation()
    await scenario_2_client_disconnects_then_tries_command() # Renamed for clarity
    await scenario_3_invalid_mcp_command()

    print("\n[INFO] All scenarios completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("[INFO] Integration tests passed successfully.")
    except Exception as e:
        print(f"[FATAL_ERROR] An unexpected error occurred at the top level: {e}")
        sys.exit(1)
