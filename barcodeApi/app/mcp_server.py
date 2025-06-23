from typing import Optional
import base64
import logging
from fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData
from fastmcp.prompts.prompt import Message, PromptMessage, TextContent

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)

logger = logging.getLogger(__name__)

global_mcp_instance = FastMCP(
    name="theBarcodeGeneratorMCP",
    instructions="This server provides barcode generation capabilities. Use the generate_barcode tool to create barcodes in various formats.",
    include_tags={"barcode", "mcp", "barcode generator", "barcode api", "barcode mcp", "barcode generation"}
)

@global_mcp_instance.prompt(
    name="generate_barcode_basic",
    description="Generate a basic barcode for the given data and format.",
    tags={"barcode", "basic", "generation"},
    enabled=True
)
def generate_barcode_basic_prompt(data: str, format: str) -> PromptMessage:
    """Prompt: Generate a barcode for the given data and format. Required parameters: data, format."""
    return PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=(
                f"Using the `generate_barcode` tool, generate a barcode for the data '{data}' in the '{format}' format. "
                "Use the standard default options for all other parameters (such as default size, colors, and output format)."
            )
        )
    )


@global_mcp_instance.prompt(
    name="generate_barcode_custom_size",
    description="Generate a barcode for the given data, format, width, and height.",
    tags={"barcode", "custom", "size"},
    enabled=True
)
def generate_barcode_custom_size_prompt(data: str, format: str, width: int, height: int) -> PromptMessage:
    """Prompt: Generate a barcode for the given data, format, width, and height."""
    return PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=(
                f"Using the `generate_barcode` tool, generate a barcode for the data '{data}' in the '{format}' format. "
                f"Set the width to {width} and the height to {height} pixels. "
                "Use the standard default options for all other parameters (such as default colors and output format)."
            )
        )
    )


@global_mcp_instance.prompt(
    name="generate_barcode_text_color",
    description="Generate a barcode with custom text and colors.",
    tags={"barcode", "text", "color"},
    enabled=True
)
def generate_barcode_text_color_prompt(data: str, format: str, text_content: str, background: str, foreground: str) -> PromptMessage:
    """Prompt: Generate a barcode with custom text and colors."""
    return PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=(
                f"Using the `generate_barcode` tool, generate a barcode for the data '{data}' in the '{format}' format. "
                f"Show the text '{text_content}', set the background to {background} and the foreground to {foreground}. "
                "Use the standard default options for all other parameters (such as default size and output format)."
            )
        )
    )


@global_mcp_instance.prompt(
    name="generate_barcode_advanced",
    description="Generate a barcode with advanced options.",
    tags={"barcode", "advanced", "options"},
    enabled=True
)
def generate_barcode_advanced_prompt(data: str, format: str, width: int, height: int, font_size: int, text_distance: float, image_format: str) -> PromptMessage:
    """Prompt: Generate a barcode with advanced options."""
    return PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=(
                f"Using the `generate_barcode` tool, generate a barcode for the data '{data}' in the '{format}' format. "
                f"Set the width to {width}, height to {height}, font size to {font_size}, text distance to {text_distance}, and output as a {image_format}. "
                "Use the standard default options for all other parameters."
            )
        )
    )


@global_mcp_instance.prompt(
    name="generate_barcode_minimal",
    description="Generate a minimal barcode.",
    tags={"barcode", "minimal"},
    enabled=True
)
def generate_barcode_minimal_prompt(data: str, format: str) -> PromptMessage:
    """Prompt: Generate a minimal barcode."""
    return PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=(
                f"Using the `generate_barcode` tool, generate a barcode for the data '{data}' in the '{format}' format. "
                "Use the standard default options for all other parameters (such as default size, colors, and output format)."
            )
        )
    )
