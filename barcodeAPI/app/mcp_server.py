from mcp.server.fastmcp import FastMCP
from typing import Optional
import base64
from io import BytesIO
from .schemas import BarcodeFormatEnum, BarcodeImageFormatEnum, BarcodeRequest
from .barcode_generator import generate_barcode_image, BarcodeGenerationError
import logging
import json

# Initialize logger
logger = logging.getLogger(__name__)
# Initialize FastMCP
mcp = FastMCP("barcode_generator_mcp")

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

    Args:
        data: The data to encode in the barcode.
        format: Barcode format (e.g., code128, ean13).
        width: Width of the barcode image in pixels (default: 200).
        height: Height of the barcode image in pixels (default: 100).
        show_text: Whether to display text under the barcode (default: True).
        text_content: Custom text to display. If None and show_text is True, uses encoded data.
        module_width: Width of one barcode module in mm.
        module_height: Height of the barcode modules in mm.
        quiet_zone: Margin space around the barcode in mm.
        font_size: Font size of the text under the barcode in pt.
        text_distance: Distance between the barcode and text in mm.
        background: Background color (e.g., 'white').
        foreground: Foreground color (e.g., 'black').
        center_text: Center the text under the barcode (default: True).
        image_format: Image file format (e.g., PNG, JPEG) (default: PNG).
        dpi: DPI for the barcode image (default: 200).
        add_checksum: Add checksum to the barcode data (specific to some formats).
        no_checksum: Do not add checksum (specific to some formats).
        guardbar: Add guardbar (specific to some formats).
    Returns:
        A base64 encoded string of the generated barcode image on success,
        or an error message string on failure.
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
            image_format=image_format, # MCP passes the enum member directly
            dpi=dpi,
            add_checksum=add_checksum,
            no_checksum=no_checksum,
            guardbar=guardbar
        )

        # Prepare writer_options, filtering out None values
        writer_options = {
            'module_width': module_width,
            'module_height': module_height,
            'quiet_zone': quiet_zone,
            'font_size': font_size if show_text else 0,
            'text_distance': text_distance if show_text else 0,
            'background': background,
            'foreground': foreground,
            'center_text': center_text,
            'image_format': image_format.value, # Pass the string value to the generator
            'dpi': dpi
        }
        if show_text and text_content:
            writer_options['text_content'] = text_content
        writer_options = {k: v for k, v in writer_options.items() if v is not None}

        # Generate barcode image bytes
        image_bytes = await generate_barcode_image(barcode_request, writer_options)
        
        # Encode image bytes as base64 string
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        logger.info(f"Barcode generated successfully for data: {data}")
        # Could return a JSON string with more details if needed,
        # but for now, returning the base64 image directly or a success message.
        # Let's return the base64 string.
        return f"data:image/{image_format.value.lower()};base64,{base64_image}"

    except BarcodeGenerationError as e:
        logger.error(f"MCP Tool: Barcode generation error for data='{data}': {str(e)}")
        return json.dumps({"error_type": e.error_type, "message": e.message})
    except Exception as e:
        logger.error(f"MCP Tool: Unexpected error for data='{data}': {str(e)}")
        return json.dumps({"error_type": "UnexpectedError", "message": f"An unexpected error occurred: {str(e)}"})

if __name__ == "__main__":
    logger.info("Starting MCP server for barcode generation...")
    # Initialize and run the server
    # The 'name' used in FastMCP("barcode_generator_mcp") should be consistent
    # if it's used by a client for discovery, but for stdio transport,
    # the execution of this script is the primary concern.
    mcp.run(transport='stdio')
    logger.info("MCP server stopped.")
