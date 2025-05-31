from typing import Optional
import base64
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData
from .schemas import BarcodeFormatEnum, BarcodeImageFormatEnum, BarcodeRequest
from .barcode_generator import generate_barcode_image, BarcodeGenerationError
import logging

# Configure basic logging (todo: move to main)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)

# Initialize logger for this module
logger = logging.getLogger(__name__)

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
        if show_text and text_content:
            writer_options['text_content'] = text_content

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
