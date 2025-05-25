import pytest
import asyncio
from unittest.mock import patch, MagicMock
from barcodeAPI.app.schemas import BarcodeFormatEnum, BarcodeImageFormatEnum
from barcodeAPI.app.mcp_server import generate_barcode_mcp
from barcodeAPI.app.barcode_generator import BarcodeGenerationError
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
    with patch('barcodeAPI.app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image:
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
    with patch('barcodeAPI.app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image:
        # Configure the mock to be an async function that raises the error
        async def async_mock_raise_error(*args, **kwargs):
            # Using the specific error message and type as per instructions
            raise BarcodeGenerationError("Test error", "TestBarcodeErrorType")
        mock_generate_image.side_effect = async_mock_raise_error

        result = await generate_barcode_mcp(
            data="error_test",
            format=BarcodeFormatEnum.ean13
        )

        error_response = json.loads(result)

        assert "error_type" in error_response
        assert error_response["error_type"] == "TestBarcodeErrorType"
        assert "message" in error_response
        assert error_response["message"] == "Test error"
        mock_generate_image.assert_called_once()

@pytest.mark.asyncio
async def test_generate_barcode_mcp_unexpected_error():
    """
    Tests error handling for unexpected errors during barcode generation.
    Mocks generate_barcode_image to raise a generic Exception.
    """
    with patch('barcodeAPI.app.mcp_server.generate_barcode_image', new_callable=MagicMock) as mock_generate_image:
        async def async_mock_raise_unexpected_error(*args, **kwargs):
            # Using the specific error message as per instructions
            raise Exception("Test unexpected error")
        mock_generate_image.side_effect = async_mock_raise_unexpected_error

        result = await generate_barcode_mcp(
            data="unexpected_error_test",
            format=BarcodeFormatEnum.upca
        )

        error_response = json.loads(result)

        assert "error_type" in error_response
        assert error_response["error_type"] == "UnexpectedError"
        assert "message" in error_response
        # Ensuring the message matches the format from mcp_server.py
        assert error_response["message"] == "An unexpected error occurred: Test unexpected error"
        mock_generate_image.assert_called_once()
