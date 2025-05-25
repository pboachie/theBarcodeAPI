from mcp.server.fastmcp import FastMCP, RpcError
from typing import Optional
import base64
from io import BytesIO
from .schemas import BarcodeFormatEnum, BarcodeImageFormatEnum, BarcodeRequest
from .barcode_generator import generate_barcode_image, BarcodeGenerationError
import logging
import json
import argparse
from app.api import mcp as mcp_api_router
from fastapi import FastAPI
from app.sse_transport import SseTransport

# Configure basic logging to capture DEBUG messages from all loggers, including MCP
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
# Explicitly set mcp library loggers to DEBUG
logging.getLogger("mcp").setLevel(logging.DEBUG)
logging.getLogger("mcp.server").setLevel(logging.DEBUG)
logging.getLogger("mcp.shared").setLevel(logging.DEBUG)


# Initialize logger for this module
logger = logging.getLogger(__name__)
sse_transport_instance = SseTransport()

# Initialize FastMCP
mcp = FastMCP("barcode_generator_mcp", transport=sse_transport_instance)


fastapi_app = FastAPI()
fastapi_app.include_router(mcp_api_router.router)

async def handle_initialize(params, client_info, session):
    """Custom handler for MCP initialize event."""
    logger.info(f"MCP Server: on_initialize triggered. ClientInfo: {client_info}, Params: {params}")
    # You can store client_info or session-specific data here if needed
    # For SSE, client_info will contain the client_id passed to process_request
    return {}

mcp.on_initialize = handle_initialize

@mcp.tool()
async def generate_barcode_mcp(
    data: str,
    format: BarcodeFormatEnum,
    width: int = 200,
    height: int = 100,
    show_text: bool = True,
    text_content: Optional[str] = None,
    module_width: Optional[float] = None,
    module_height: Optional[float] = None,
    quiet_zone: Optional[float] = None,
    font_size: Optional[int] = None,
    text_distance: Optional[float] = None,
    background: Optional[str] = None,
    foreground: Optional[str] = None,
    center_text: bool = True,
    image_format: BarcodeImageFormatEnum = BarcodeImageFormatEnum.PNG,
    dpi: int = 200,
    add_checksum: Optional[bool] = None,
    no_checksum: Optional[bool] = None,
    guardbar: Optional[bool] = None
) -> str:
    """
    Generates a barcode image based on the provided parameters and returns a status message
    or a base64 encoded image string.
    """
    logger.info(f"MCP Tool: generate_barcode_mcp called with data='{data}', format='{format.value}'")
    try:
        barcode_request = BarcodeRequest(
            data=data,
            format=format,
            width=width,
            height=height,
            show_text=show_text,
            text_content=text_content if show_text else "",
            module_width=module_width,
            module_height=module_height,
            quiet_zone=quiet_zone,
            font_size=font_size if show_text else 0,
            text_distance=text_distance if show_text else 0,
            background=background,
            foreground=foreground,
            center_text=center_text,
            image_format=image_format,
            dpi=dpi,
            add_checksum=add_checksum,
            no_checksum=no_checksum,
            guardbar=guardbar
        )

        writer_options = {
            'module_width': module_width,
            'module_height': module_height,
            'quiet_zone': quiet_zone,
            'font_size': font_size if show_text else 0,
            'text_distance': text_distance if show_text else 0,
            'background': background,
            'foreground': foreground,
            'center_text': center_text,
            'image_format': image_format.value,
            'dpi': dpi
        }
        if show_text and text_content:
            writer_options['text_content'] = text_content
        writer_options = {k: v for k, v in writer_options.items() if v is not None}

        image_bytes = await generate_barcode_image(barcode_request, writer_options)
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        logger.info(f"Barcode generated successfully for data: {data}")
        return f"data:image/{image_format.value.lower()};base64,{base64_image}"

    except BarcodeGenerationError as e:
        logger.error(f"MCP Tool: Barcode generation error for data='{data}': {str(e)}")
        # Raise an RpcError that FastMCP can convert to a standard JSON-RPC error response
        raise RpcError(code=-32000, message=e.message, data={"type": e.error_type})
    except Exception as e:
        logger.error(f"MCP Tool: Unexpected error for data='{data}': {str(e)}", exc_info=True)
        raise RpcError(code=-32001, message=f"An unexpected error occurred: {str(e)}", data={"type": "UnexpectedError"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "http", "tcp"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    logger.info(f"Starting MCP server for barcode generation with transport: {args.transport}")

    if args.transport == "sse" or args.transport == "http":
        try:
            import uvicorn
        except ImportError:
            logger.error("uvicorn is not installed. Please install it with 'pip install uvicorn' to use sse or http transport.")
            exit(1)

        if args.transport == "sse":
            logger.info(f"Starting FastAPI server with SSE on http://{args.host}:{args.port}/sse")
        else: # http
            logger.info(f"Starting FastAPI server (generic HTTP) on http://{args.host}:{args.port}")
            logger.warning("HTTP transport mode currently serves the same FastAPI app as SSE, including the /sse endpoint.")
            logger.warning("For a dedicated MCP-over-HTTP (non-SSE) transport, FastMCP's HTTP server or a custom FastAPI POST endpoint would be needed.")

        # The 'mcp' instance is already configured with SseTransport.
        # The FastAPI app (via mcp_api_router) will use this 'mcp' instance.
        # SseTransport will handle routing responses from mcp.process_request to the correct client.
        uvicorn.run("app.mcp_server:fastapi_app", host=args.host, port=args.port, reload=False)

    elif args.transport == "tcp":
        logger.info(f"Starting MCP server with TCP transport on {args.host}:{args.port}")
        # When mcp.run is called with transport='tcp', it uses FastMCP's internal TCP handling.
        # The SseTransport instance passed to the constructor will not be used for this server loop.
        mcp.run(transport="tcp", host=args.host, port=args.port)

    else:  # stdio
        logger.info("Starting MCP server with stdio transport")
        mcp.run(transport="stdio")

    logger.info("MCP server stopped.")
