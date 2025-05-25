import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.schemas import BarcodeFormatEnum, BarcodeImageFormatEnum # Corrected
from app.mcp_server import generate_barcode_mcp # Corrected
from app.barcode_generator import BarcodeGenerationError # Corrected
from mcp.shared.exceptions import McpError # Added
from mcp.types import ErrorData # Added
import base64
import json

@pytest.mark.asyncio
async def test_generate_barcode_mcp_success():
    """
    Tests successful barcode generation via the MCP tool.
    Mocks generate_barcode_image to return sample image bytes.
    """
    mock_image_bytes = b'fakeimagedata'

    # Path to the function to be mocked is within mcp_server where it's called
    with patch('app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image: # Corrected
        # Configure the mock to be an async function that returns our fake image bytes
        async def async_mock_return(*args, **kwargs):
            return mock_image_bytes
        mock_generate_image.side_effect = async_mock_return

        result = await generate_barcode_mcp(
            data="test12345",
            format=BarcodeFormatEnum.code128,
            image_format=BarcodeImageFormatEnum.PNG
        )

        assert result.startswith("data:image/png;base64,")
        base64_encoded_data = result.split(",")[1]
        decoded_data = base64.b64decode(base64_encoded_data)
        assert decoded_data == mock_image_bytes
        mock_generate_image.assert_called_once()

@pytest.mark.asyncio
async def test_generate_barcode_mcp_generation_error():
    """
    Tests error handling when barcode generation fails.
    Mocks generate_barcode_image to raise BarcodeGenerationError.
    """
    # Path to the function to be mocked
    with patch('app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image: # Corrected
        # Configure the mock to be an async function that raises the error
        async def async_mock_raise_error(*args, **kwargs):
            # Using the specific error message and type as per instructions
            raise BarcodeGenerationError("Test error", "TestBarcodeErrorType")
        mock_generate_image.side_effect = async_mock_raise_error

        with pytest.raises(McpError) as excinfo:
            await generate_barcode_mcp(
                data="123456789012", # Valid EAN-13 data
                format=BarcodeFormatEnum.ean13
            )
        
        assert excinfo.value.error.code == -32000
        assert excinfo.value.error.message == "Test error"
        assert excinfo.value.error.data == {"type": "TestBarcodeErrorType"}
        mock_generate_image.assert_called_once()

@pytest.mark.asyncio
async def test_generate_barcode_mcp_unexpected_error():
    """
    Tests error handling for unexpected errors during barcode generation.
    Mocks generate_barcode_image to raise a generic Exception.
    """
    with patch('app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image: # Corrected
        async def async_mock_raise_unexpected_error(*args, **kwargs):
            # Using the specific error message as per instructions
            raise Exception("Test unexpected error")
        mock_generate_image.side_effect = async_mock_raise_unexpected_error

        with pytest.raises(McpError) as excinfo:
            await generate_barcode_mcp(
                data="12345678901", # Valid UPC-A data
                format=BarcodeFormatEnum.upca
            )
        
        assert excinfo.value.error.code == -32001
        assert excinfo.value.error.message == "An unexpected error occurred: Test unexpected error"
        assert excinfo.value.error.data == {"type": "UnexpectedError"}
        mock_generate_image.assert_called_once()
