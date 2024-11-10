# app/barcode_generator.py

import asyncio
from io import BytesIO
from barcode import get_barcode_class
from barcode.writer import ImageWriter
from barcode.errors import BarcodeError
from app.schemas import BarcodeRequest, BarcodeGenerationError
from typing import Dict
import logging
import PIL.Image
from PIL import Image

logger = logging.getLogger(__name__)


async def generate_barcode_image(barcode_request: BarcodeRequest, writer_options: Dict[str, any]) -> bytes:
    return await asyncio.to_thread(_generate_barcode_image_sync, barcode_request, writer_options)


def _generate_barcode_image_sync(barcode_request: BarcodeRequest, writer_options: Dict[str, any]) -> bytes:
    try:
        barcode_class = get_barcode_class(barcode_request.format)

        # Create ImageWriter with specific options
        writer = ImageWriter()
        for key, value in writer_options.items():
            if hasattr(writer, key):
                setattr(writer, key, value)

        # Create barcode instance with options
        barcode_options = {}
        if barcode_request.format == 'code39':
            if 'add_checksum' in writer_options:
                barcode_options['add_checksum'] = writer_options['add_checksum']
        elif barcode_request.format == 'ean13':
            if 'no_checksum' in writer_options:
                barcode_options['no_checksum'] = writer_options['no_checksum']
            if 'guardbar' in writer_options:
                barcode_options['guardbar'] = writer_options['guardbar']

        barcode = barcode_class(barcode_request.data, writer=writer, **barcode_options)

        buffer = BytesIO()
        barcode.write(buffer)

        # Open the image using Pillow(-SIMD)
        buffer.seek(0)
        img = PIL.Image.open(buffer)

        # Validate DPI
        if barcode_request.dpi > 600:
            logger.warning("DPI value is unusually high; adjusting to 600.")
            barcode_request.dpi = 600

        # Resize the image
        img = img.resize((barcode_request.width, barcode_request.height), PIL.Image.LANCZOS)

        # Save the resized image to a new buffer
        try:
            with BytesIO() as new_buffer:
                img.save(new_buffer, format=writer_options.get('image_format', 'PNG'), optimize=True)
                new_buffer.seek(0)
                return new_buffer.getvalue()
        except Exception as e:
            raise BarcodeGenerationError(f"Error generating barcode: {str(e)}", "UnexpectedError")
        finally:
            img.close()
            buffer.close()

    except BarcodeError as e:
        logger.error(f"Barcode generation error: {str(e)}")
        raise BarcodeGenerationError(str(e), "BarcodeError")
    except ValueError as e:
        logger.error(f"Value error in barcode generation: {str(e)}")
        raise BarcodeGenerationError(str(e), "ValueError")
    except TypeError as e:
        logger.error(f"Type error in barcode generation: {str(e)}")
        raise BarcodeGenerationError(f"Invalid options for barcode format {barcode_request.format}", "TypeError")
    except Exception as e:
        logger.error(f"Unexpected error in barcode generation: {str(e)}")
        raise BarcodeGenerationError(f"An unexpected error occurred during barcode generation: {str(e)}", "UnexpectedError")