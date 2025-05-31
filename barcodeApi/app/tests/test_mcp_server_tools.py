import pytest
import asyncio
import base64
from unittest.mock import AsyncMock, patch, call

# Functions and classes to be tested or used in tests
from app.mcp_server import generate_barcode_mcp
from app.schemas import BarcodeRequest, BarcodeFormatEnum, BarcodeImageFormatEnum
from app.barcode_generator import BarcodeGenerationError
# from mcp.server.fastmcp import RpcError # Old import removed
from mcp.shared.exceptions import McpError # New import
from mcp.types import ErrorData # New import

# Default values for assertion, derived from function signature if not overridden
DEFAULT_WIDTH = 200
DEFAULT_HEIGHT = 100
DEFAULT_SHOW_TEXT = True
DEFAULT_IMAGE_FORMAT = BarcodeImageFormatEnum.PNG
DEFAULT_DPI = 200

@pytest.mark.asyncio
@patch('app.mcp_server.generate_barcode_image', new_callable=AsyncMock)
async def test_generate_barcode_mcp_successful(mock_generate_image: AsyncMock):
    """Test successful barcode generation by the MCP tool."""
    mock_generate_image.return_value = b'fakedata'
    
    data = "123456789012" # Corrected to 12 digits for EAN-13
    barcode_format = BarcodeFormatEnum.ean13 # Corrected to lowercase
    image_format = BarcodeImageFormatEnum.JPEG # Remains uppercase as per schema
    
    result = await generate_barcode_mcp(
        data=data,
        format=barcode_format,
        width=300,
        height=150,
        show_text=False,
        text_content="CustomText", # Will be ignored if show_text is False in BarcodeRequest logic
        image_format=image_format,
        dpi=300
    )
    
    expected_barcode_request = BarcodeRequest(
        data=data,
        format=barcode_format,
        width=300,
        height=150,
        show_text=False,
        text_content="", # Because show_text is False
        image_format=image_format,
        dpi=300
        # Other fields will use defaults from BarcodeRequest Pydantic model
    )
    
    # Expected options AFTER None values are filtered by generate_barcode_mcp
    expected_writer_options = {
        'font_size': 0,
        'text_distance': 0,
        'center_text': True,
        'image_format': BarcodeImageFormatEnum.JPEG.value,
        'dpi': 300
    }
    
    mock_generate_image.assert_awaited_once()
    # Check BarcodeRequest object (first positional argument)
    actual_barcode_request_arg = mock_generate_image.call_args[0][0]
    assert isinstance(actual_barcode_request_arg, BarcodeRequest)
    # Compare relevant fields as BarcodeRequest might have more defaults
    assert actual_barcode_request_arg.data == expected_barcode_request.data
    assert actual_barcode_request_arg.format == expected_barcode_request.format
    assert actual_barcode_request_arg.width == expected_barcode_request.width
    assert actual_barcode_request_arg.height == expected_barcode_request.height
    assert actual_barcode_request_arg.show_text == expected_barcode_request.show_text
    assert actual_barcode_request_arg.text_content == expected_barcode_request.text_content # Should be ""
    assert actual_barcode_request_arg.image_format == expected_barcode_request.image_format
    assert actual_barcode_request_arg.dpi == expected_barcode_request.dpi

    # Check writer_options (second positional argument)
    assert mock_generate_image.call_args[0][1] == expected_writer_options
    
    expected_base64 = base64.b64encode(b'fakedata').decode('utf-8')
    assert result == f"data:image/{image_format.value.lower()};base64,{expected_base64}"

@pytest.mark.asyncio
@patch('app.mcp_server.generate_barcode_image', new_callable=AsyncMock)
async def test_generate_barcode_mcp_barcode_generation_error(mock_generate_image: AsyncMock):
    """Test handling of BarcodeGenerationError."""
    error_message = "Test barcode generation error"
    error_type = "CustomErrorType123"
    mock_generate_image.side_effect = BarcodeGenerationError(error_message, error_type)
    
    with pytest.raises(McpError) as excinfo:
        await generate_barcode_mcp(data="testdata", format=BarcodeFormatEnum.gs1) # Assuming 'gs1' is a valid lowercase member, previously was QR
        
    assert excinfo.value.error.code == -32000
    assert excinfo.value.error.message == error_message
    assert excinfo.value.error.data == {"type": error_type}

@pytest.mark.asyncio
@patch('app.mcp_server.generate_barcode_image', new_callable=AsyncMock)
async def test_generate_barcode_mcp_unexpected_error(mock_generate_image: AsyncMock):
    """Test handling of unexpected errors."""
    error_message = "Something went very wrong"
    mock_generate_image.side_effect = Exception(error_message)
    
    with pytest.raises(McpError) as excinfo:
        await generate_barcode_mcp(data="12345678901", format=BarcodeFormatEnum.upca) # Corrected to 11 digits for UPC-A
        
    assert excinfo.value.error.code == -32001
    assert excinfo.value.error.message == f"An unexpected error occurred: {error_message}"
    assert excinfo.value.error.data == {"type": "UnexpectedError"}

@pytest.mark.asyncio
@patch('app.mcp_server.generate_barcode_image', new_callable=AsyncMock)
async def test_generate_barcode_mcp_parameter_defaults_and_options(mock_generate_image: AsyncMock):
    """Test default parameter handling and option overrides."""
    mock_generate_image.return_value = b'fakedata_defaults'
    
    # Call 1: Minimal parameters, check defaults
    data_min = "minimal"
    format_min = BarcodeFormatEnum.code128 # Corrected to lowercase
    
    await generate_barcode_mcp(data=data_min, format=format_min)
    
    expected_barcode_request_min = BarcodeRequest(
        data=data_min,
        format=format_min,
        width=DEFAULT_WIDTH, # Default from function signature
        height=DEFAULT_HEIGHT, # Default from function signature
        show_text=DEFAULT_SHOW_TEXT, # Default from function signature
        text_content=None, # Corrected expectation for text_content
        image_format=DEFAULT_IMAGE_FORMAT, # Default from function signature
        dpi=DEFAULT_DPI, # Default from function signature
    )
    
    # Expected options AFTER None values are filtered by generate_barcode_mcp
    expected_writer_options_min = {
        'center_text': True,
        'image_format': BarcodeImageFormatEnum.PNG.value,
        'dpi': 200
    }

    # First call assertions
    mock_generate_image.assert_awaited_once()
    actual_br_min = mock_generate_image.call_args[0][0]
    actual_wo_min = mock_generate_image.call_args[0][1]

    assert actual_br_min.data == expected_barcode_request_min.data
    assert actual_br_min.format == expected_barcode_request_min.format
    assert actual_br_min.width == expected_barcode_request_min.width
    assert actual_br_min.height == expected_barcode_request_min.height
    assert actual_br_min.show_text == expected_barcode_request_min.show_text
    assert actual_br_min.text_content == expected_barcode_request_min.text_content
    assert actual_br_min.image_format == expected_barcode_request_min.image_format
    assert actual_br_min.dpi == expected_barcode_request_min.dpi
    assert actual_wo_min == expected_writer_options_min
    
    mock_generate_image.reset_mock() # Reset for the second call
    
    # Call 2: Specific options overridden
    mock_generate_image.return_value = b'fakedata_overrides'
    data_override = "override_params"
    format_override = BarcodeFormatEnum.itf # Corrected to lowercase
    
    await generate_barcode_mcp(
        data=data_override,
        format=format_override,
        show_text=False,
        text_content="This text is present but show_text is False", # Should be ignored
        font_size=12, # Should be passed as 0 if show_text is False
        module_width=0.5,
        quiet_zone=10.0,
        background="blue",
        center_text=False
    )
    
    expected_barcode_request_override = BarcodeRequest(
        data=data_override,
        format=format_override,
        width=DEFAULT_WIDTH, # Default as not overridden
        height=DEFAULT_HEIGHT, # Default as not overridden
        show_text=False,
        text_content="", # text_content in BarcodeRequest becomes "" if show_text is False
        module_width=0.5,
        quiet_zone=10.0,
        font_size=0, # font_size in BarcodeRequest becomes 0 if show_text is False
        background="blue",
        center_text=False,
        image_format=DEFAULT_IMAGE_FORMAT, # Default
        dpi=DEFAULT_DPI # Default
    )
    
    # Expected options AFTER None values are filtered by generate_barcode_mcp
    expected_writer_options_override = {
        'module_width': 0.5,
        'quiet_zone': 10.0,
        'font_size': 0,
        'text_distance': 0,
        'background': "blue",
        'center_text': False,
        'image_format': BarcodeImageFormatEnum.PNG.value,
        'dpi': 200
    }

    # Second call assertions
    mock_generate_image.assert_awaited_once()
    actual_br_override = mock_generate_image.call_args[0][0]
    actual_wo_override = mock_generate_image.call_args[0][1]

    assert actual_br_override.data == expected_barcode_request_override.data
    assert actual_br_override.format == expected_barcode_request_override.format
    assert actual_br_override.show_text == expected_barcode_request_override.show_text
    assert actual_br_override.text_content == expected_barcode_request_override.text_content
    assert actual_br_override.module_width == expected_barcode_request_override.module_width
    assert actual_br_override.quiet_zone == expected_barcode_request_override.quiet_zone
    assert actual_br_override.font_size == expected_barcode_request_override.font_size
    assert actual_br_override.background == expected_barcode_request_override.background
    assert actual_br_override.center_text == expected_barcode_request_override.center_text
    
    # Comparing the whole dict for writer options
    assert actual_wo_override == expected_writer_options_override
