import httpx
import asyncio
import json
import uuid
import sys
from typing import Optional

BASE_URL = "http://127.0.0.1:8000" # Assuming API runs on port 8000
HTTP_MCP_URL = f"{BASE_URL}/mcp"
SSE_MCP_URL = f"{BASE_URL}/mcp/sse"

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

async def send_mcp_command_for_sse_session(client: httpx.AsyncClient, method: str, params: dict, request_id: str, token: Optional[str] = None):
    """
    Sends an MCP command (JSON-RPC request) via POST to the SSE_MCP_URL.
    This is how FastMCP handles commands for an active SSE session.
    The server identifies the client session from the HTTP connection context.
    """
    mcp_request_payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print_step(f"Sending MCP command for SSE session to {SSE_MCP_URL}: {json.dumps(mcp_request_payload)}")
    response = await client.post(SSE_MCP_URL, json=mcp_request_payload, headers=headers)

    # FastMCP's POST to the SSE URL for an active session usually returns 200 OK (often with an empty body)
    # if the command is accepted for processing. The actual JSON-RPC response comes via the SSE stream.
    # An immediate JSON-RPC error might be returned here if the request itself is malformed before processing.
    print_assertion(f"MCP command POST to {SSE_MCP_URL} status is 200 or similar success", response.status_code in [200, 202, 204] or response.headers.get('content-type') == 'application/json')
    if response.status_code not in [200, 202, 204] and response.headers.get('content-type') != 'application/json':
        print(f"MCP Command POST Response (unexpected): {response.status_code} - {response.text}")
    # If it's an immediate JSON-RPC error, it will be handled by the caller checking the SSE stream or this response.
    return response

async def send_mcp_http_request(client: httpx.AsyncClient, method: str, params: dict, request_id: str, token: Optional[str] = None):
    """Sends an MCP request to the HTTP_MCP_URL and expects a direct JSON-RPC response."""
    mcp_request_payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print_step(f"Sending MCP request to {HTTP_MCP_URL}: {json.dumps(mcp_request_payload)}")
    response = await client.post(HTTP_MCP_URL, json=mcp_request_payload, headers=headers)

    print_assertion(f"MCP HTTP request to {HTTP_MCP_URL} content type is application/json", response.headers.get("content-type") == "application/json")
    # The response status code might vary for JSON-RPC (e.g., 200 for success, 200 or 4xx/5xx for errors in JSON-RPC response body)
    # For now, we just check content type and let caller parse JSON-RPC.
    return response

async def scenario_sse_successful_barcode_generation(): # Renamed from scenario_1
    print_step("Starting Scenario SSE: Successful Barcode Generation")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_MCP_URL}")
            async with client.stream("GET", SSE_MCP_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)

                client_id = await get_client_id_from_sse(client, sse_response) # client_id is mostly for conceptual clarity now
                if client_id is None: # Handle None case
                    print_assertion("Failed to get client_id for SSE successful generation", False) # More specific message
                    return

                request_id = str(uuid.uuid4())
                method = "generate_barcode"
                params = {
                    "data": "123456789012",
                    "format": "EAN13",
                    "image_format": "PNG",
                    "show_text": True
                }

                # Using the correctly named helper
                await send_mcp_command_for_sse_session(client, method, params, request_id)

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
            print_assertion(f"An unexpected error occurred in SSE successful generation: {e}", False) # More specific

async def scenario_sse_client_disconnects_then_tries_command(): # Renamed
    print_step("Starting Scenario SSE: Client Disconnects, then tries command (should fail)")
    async with httpx.AsyncClient(timeout=10.0) as client:
        original_client_id: Optional[str] = None
        try:
            # 1. Connect and get a client_id (client_id is just for logging/conceptual clarity with FastMCP)
            print_step(f"Connecting to SSE endpoint: {SSE_MCP_URL} to get client_id context")
            async with client.stream("GET", SSE_MCP_URL) as sse_response: # Corrected URL
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)
                original_client_id = await get_client_id_from_sse(client, sse_response)
            print_step(f"SSE connection closed after getting client_id context: {original_client_id}")
            print_assertion("Client ID context was obtained", original_client_id is not None)

            # 2. Try to send a command. FastMCP should reject this as the SSE connection is gone.
            print_step(f"Attempting to send MCP command with stale/disconnected client context to {SSE_MCP_URL}")
            request_id = str(uuid.uuid4())

            # This POST should ideally fail because the original connection that established the session is closed.
            # FastMCP might return an error if it can't find an active session for the command.
            # The send_mcp_command_for_sse_session itself might not be the best fit here if we expect immediate POST failure
            # rather than an SSE response. Let's just POST directly.
            cmd_response = await client.post(SSE_MCP_URL, json={ # Corrected URL
                "jsonrpc": "2.0", "method": "generate_barcode", "params": {}, "id": request_id
            }, headers={"Content-Type": "application/json"})

            # Expecting an error because there's no active SSE session.
            # FastMCP might return 400, 403, 404, or a JSON-RPC error directly in the POST response.
            print_assertion(f"Command POST to {SSE_MCP_URL} for disconnected client should fail (e.g., status >= 400 or JSON RPC error in response)",
                            cmd_response.status_code >= 400 or "error" in cmd_response.json())
            if cmd_response.status_code < 400 and "error" not in cmd_response.json():
                print(f"Unexpected success on command POST: {cmd_response.text}")
            else:
                print(f"Received expected error status {cmd_response.status_code} or JSON error: {cmd_response.text}")

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in SSE client disconnects scenario: {e}", False) # More specific

async def scenario_sse_invalid_mcp_command(): # Renamed
    print_step("Starting Scenario SSE: Invalid MCP Command (Method not found)")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_MCP_URL}") # Corrected URL
            async with client.stream("GET", SSE_MCP_URL) as sse_response: # Corrected URL
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)

                client_id = await get_client_id_from_sse(client, sse_response)
                if client_id is None:
                    print_assertion("Failed to get client_id for SSE invalid command", False) # More specific
                    return
                request_id = str(uuid.uuid4())

                await send_mcp_command_for_sse_session(client, "unknown_method_12345", {}, request_id) # Corrected helper

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
            print_assertion(f"An unexpected error occurred in SSE invalid command: {e}", False) # More specific

async def scenario_sse_request_with_token():
    print_step("Starting Scenario SSE: Request with (Unvalidated) Token")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            print_step(f"Connecting to SSE endpoint: {SSE_MCP_URL}")
            async with client.stream("GET", SSE_MCP_URL) as sse_response:
                if sse_response.status_code != 200:
                    raw_content = await sse_response.aread()
                    print_assertion(f"SSE connection failed with status {sse_response.status_code}. Response: {raw_content.decode()}", False)
                    return

                client_id = await get_client_id_from_sse(client, sse_response)
                if client_id is None:
                    print_assertion("Failed to get client_id for SSE token test", False)
                    return

                request_id = str(uuid.uuid4())
                method = "generate_barcode"
                params = {"data": "SSE Token Test", "format": "CODE39"}

                # Send command with token
                await send_mcp_command_for_sse_session(client, method, params, request_id, token="FAKE_SSE_MCP_TOKEN")

                print_step("Listening on SSE stream for JSON-RPC response (token should not break it)...")
                mcp_response_received = False
                async for event in sse_response.aiter_sse():
                    if event.event == "mcp_response":
                        try:
                            response_data = json.loads(event.data)
                            print_assertion("MCP response 'id' matches request 'id'", response_data.get("id") == request_id)
                            print_assertion("MCP response contains 'result'", "result" in response_data)
                            mcp_response_received = True
                            break
                        except Exception as e:
                            print_assertion(f"Error processing mcp_response for SSE token test: {e}", False)
                print_assertion("MCP response was received via SSE (token test)", mcp_response_received)

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in SSE request with token: {e}", False)

async def scenario_http_successful_barcode_generation():
    print_step("Starting Scenario HTTP: Successful Barcode Generation")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            request_id = str(uuid.uuid4())
            method = "generate_barcode"
            params = {
                "data": "HTTP Test 123",
                "format": "QRCODE",
                "image_format": "PNG",
                "show_text": False
            }
            response = await send_mcp_http_request(client, method, params, request_id)

            print_assertion("HTTP response status code is 200", response.status_code == 200)
            response_data = response.json()

            print_assertion("Response is valid JSON-RPC", response_data.get("jsonrpc") == "2.0")
            print_assertion("Response 'id' matches request 'id'", response_data.get("id") == request_id)
            print_assertion("Response contains 'result'", "result" in response_data)
            if "result" in response_data:
                result_value = response_data["result"]
                print_assertion("Result is a string (base64 image)", isinstance(result_value, str))
                print_assertion("Result starts with 'data:image/png;base64,'", result_value.startswith("data:image/png;base64,"))
                print(f"Received base64 image string (first 50 chars): {result_value[:50]}...")

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in HTTP successful generation: {e}", False)

async def scenario_http_invalid_mcp_command():
    print_step("Starting Scenario HTTP: Invalid MCP Command (Method not found)")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            request_id = str(uuid.uuid4())
            response = await send_mcp_http_request(client, "non_existent_method_abc", {}, request_id)

            print_assertion("HTTP response status code is 200 (for JSON-RPC error response)", response.status_code == 200) # FastMCP often returns 200 OK for JSON-RPC errors
            response_data = response.json()

            print_assertion("Response is valid JSON-RPC", response_data.get("jsonrpc") == "2.0")
            print_assertion("Response 'id' matches request 'id'", response_data.get("id") == request_id)
            print_assertion("Response contains 'error' object", "error" in response_data)
            if "error" in response_data:
                error_obj = response_data["error"]
                print_assertion("Error code is -32601 (Method not found)", error_obj.get("code") == -32601)
                print(f"Received error: code={error_obj.get('code')}, message='{error_obj.get('message')}'")

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in HTTP invalid command: {e}", False)

async def scenario_http_request_with_token():
    print_step("Starting Scenario HTTP: Request with (Unvalidated) Token")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            request_id = str(uuid.uuid4())
            method = "generate_barcode"
            params = {"data": "HTTP Token Test", "format": "CODE128"}
            # Assuming token is not strictly validated for MCP endpoint for now, so this should pass
            response = await send_mcp_http_request(client, method, params, request_id, token="FAKE_MCP_TOKEN")

            print_assertion("HTTP response status code is 200", response.status_code == 200)
            response_data = response.json()

            print_assertion("Response 'id' matches request 'id'", response_data.get("id") == request_id)
            print_assertion("Response contains 'result' (token did not break it)", "result" in response_data)

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in HTTP with token: {e}", False)

async def scenario_http_malformed_json_rpc():
    print_step("Starting Scenario HTTP: Malformed JSON-RPC Request")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Sending a malformed JSON string
            malformed_payload_str = '{"jsonrpc": "2.0", "method": "foo", "params": "bar", "id": 1,' # Missing closing brace
            headers = {"Content-Type": "application/json"}

            print_step(f"Sending malformed JSON request to {HTTP_MCP_URL}")
            response = await client.post(HTTP_MCP_URL, content=malformed_payload_str, headers=headers)

            # Expecting a JSON-RPC error like -32700 Parse error or -32600 Invalid Request
            # Status code might be 400 from server or 200 with JSON-RPC error payload
            print_assertion("HTTP response status code indicates error (e.g. 400 or 200 for JSON-RPC error)", response.status_code == 400 or response.status_code == 200)

            response_data = response.json()
            print_assertion("Response is valid JSON-RPC error structure", response_data.get("jsonrpc") == "2.0")
            print_assertion("Response contains 'error' object", "error" in response_data)
            if "error" in response_data:
                error_obj = response_data["error"]
                # -32700 for parse error, -32600 for invalid JSON-RPC (e.g. missing fields)
                print_assertion("Error code is -32700 or -32600", error_obj.get("code") in [-32700, -32600])
                print(f"Received error: code={error_obj.get('code')}, message='{error_obj.get('message')}'")
            # The ID might be null in case of parse errors before ID could be read.
            print_assertion("Response 'id' is null for parse error or matches if parsable", response_data.get("id") is None or isinstance(response_data.get("id"), (str, int)))

        except httpx.ConnectError as e:
            print_assertion(f"Connection to server failed: {e}. Ensure the server is running at {BASE_URL}.", False)
        except Exception as e:
            print_assertion(f"An unexpected error occurred in HTTP malformed JSON: {e}", False)

async def main():
    print_step("Starting MCP Endpoint Integration Tests")

    # --- HTTP Tests ---
    print_step("--- Running HTTP MCP Endpoint Tests ---")
    await scenario_http_successful_barcode_generation()
    await scenario_http_invalid_mcp_command()
    await scenario_http_request_with_token()
    await scenario_http_malformed_json_rpc()

    # --- SSE Tests ---
    print_step("--- Running SSE MCP Endpoint Tests ---")
    await scenario_sse_successful_barcode_generation()
    await scenario_sse_client_disconnects_then_tries_command()
    await scenario_sse_invalid_mcp_command()
    await scenario_sse_request_with_token()

    print("\n[INFO] All scenarios completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("[INFO] Integration tests passed successfully.")
    except Exception as e:
        print(f"[FATAL_ERROR] An unexpected error occurred at the top level: {e}")
        sys.exit(1)
