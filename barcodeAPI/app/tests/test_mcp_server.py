import pytest
import asyncio
from unittest.mock import patch, MagicMock
from barcodeAPI.app.schemas import BarcodeFormatEnum, BarcodeImageFormatEnum
from barcodeAPI.app.mcp_server import generate_barcode_mcp
from barcodeAPI.app.barcode_generator import BarcodeGenerationError # Ensure this is the correct path
import base64

@pytest.mark.asyncio
async def test_generate_barcode_mcp_success():
    """
    Tests successful barcode generation via the MCP tool.
    Mocks generate_barcode_image to return sample image bytes.
    """
    mock_image_bytes = b'fakeimagedata'
    
    # Path to the function to be mocked is within mcp_server where it's called
    with patch('barcodeAPI.app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image:
        # Configure the mock to be an async function that returns our fake image bytes
        async def async_mock_return(*args, **kwargs):
            return mock_image_bytes
        mock_generate_image.side_effect = async_mock_return

        result = await generate_barcode_mcp(
            data="test12345",
            format=BarcodeFormatEnum.code128,
            image_format=BarcodeImageFormatEnum.PNG # Ensure this is passed for the data URI
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
    with patch('barcodeAPI.app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image:
        # Configure the mock to be an async function that raises the error
        async def async_mock_raise_error(*args, **kwargs):
            raise BarcodeGenerationError("Test generation error", "test_error_type")
        mock_generate_image.side_effect = async_mock_raise_error

        result = await generate_barcode_mcp(
            data="error_test",
            format=BarcodeFormatEnum.ean13
        )

        assert result.startswith("Error generating barcode:")
        assert "Test generation error" in result
        mock_generate_image.assert_called_once()

@pytest.mark.asyncio
async def test_generate_barcode_mcp_unexpected_error():
    """
    Tests error handling for unexpected errors during barcode generation.
    Mocks generate_barcode_image to raise a generic Exception.
    """
    with patch('barcodeAPI.app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image:
        async def async_mock_raise_unexpected_error(*args, **kwargs):
            raise Exception("Unexpected test error")
        mock_generate_image.side_effect = async_mock_raise_unexpected_error

        result = await generate_barcode_mcp(
            data="unexpected_error_test",
            format=BarcodeFormatEnum.upca
        )
        
        assert result.startswith("Unexpected error:")
        assert "Unexpected test error" in result
        mock_generate_image.assert_called_once()
