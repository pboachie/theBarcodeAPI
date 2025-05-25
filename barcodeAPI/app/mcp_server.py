from typing import Optional # RpcError import removed
import base64
# from io import BytesIO # Not used directly in the new version
from mcp.shared.exceptions import McpError # Added
from mcp.types import ErrorData # Added
from .schemas import BarcodeFormatEnum, BarcodeImageFormatEnum, BarcodeRequest
from .barcode_generator import generate_barcode_image, BarcodeGenerationError
import logging
# import json # Not used directly
# import argparse # Not used directly
# from app.api import mcp as mcp_api_router # Not used directly
# from fastapi import FastAPI # Not used directly
# from app.sse_transport import SseTransport # SseTransport is not instantiated here

# Configure basic logging (can be kept or moved to main)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
# Explicitly set mcp library loggers to DEBUG (can be kept or moved to main)
logging.getLogger("mcp").setLevel(logging.DEBUG)
logging.getLogger("mcp.server").setLevel(logging.DEBUG)
logging.getLogger("mcp.shared").setLevel(logging.DEBUG)


# Initialize logger for this module
logger = logging.getLogger(__name__)

# This function can be imported and registered with an MCP instance in main.py
async def handle_initialize(params, client_info, session):
    """Custom handler for MCP initialize event."""
    logger.info(f"MCP Server: on_initialize triggered. ClientInfo: {client_info}, Params: {params}")
    # You can store client_info or session-specific data here if needed
    # For SSE, client_info will contain the client_id passed to process_request
    return {}

# The tool function, no longer decorated here. Will be registered in main.py.
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
    This function is intended to be registered as an MCP tool.
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
        if show_text and text_content: # Only add text_content to writer_options if show_text is True and text_content is provided
            writer_options['text_content'] = text_content
        
        # Remove None values from writer_options as generate_barcode_image expects them to be absent if not set
        writer_options = {k: v for k, v in writer_options.items() if v is not None}


        image_bytes = await generate_barcode_image(barcode_request, writer_options)
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        logger.info(f"Barcode generated successfully for data: {data}")
        return f"data:image/{image_format.value.lower()};base64,{base64_image}"

    except BarcodeGenerationError as e:
        logger.error(f"MCP Tool: Barcode generation error for data='{data}': {str(e)}")
        error_payload = ErrorData(code=-32000, message=e.message, data={"type": e.error_type})
        raise McpError(error_payload)
    except Exception as e:
        logger.error(f"MCP Tool: Unexpected error for data='{data}': {str(e)}", exc_info=True)
        error_payload = ErrorData(code=-32001, message=f"An unexpected error occurred: {str(e)}", data={"type": "UnexpectedError"})
        raise McpError(error_payload)

# The if __name__ == "__main__": block has been removed.
# This file now primarily defines the tool logic and can be imported by main.py.
