# app/barcode_generator.py

import asyncio
from io import BytesIO
from barcode import get_barcode_class, generate
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
        # Create ImageWriter instance first
        writer = ImageWriter()

        # Configure text settings BEFORE generating barcode
        show_text = getattr(barcode_request, 'show_text', True)
        if not show_text:
            # Disable text completely
            writer.text = ""
            writer.font_size = 0
            writer.text_distance = 0
        else:
            # Set custom text if provided, otherwise use barcode data
            writer.text = writer_options.get('text_content', barcode_request.data)
            writer.font_size = writer_options.get('font_size', 10)
            writer.text_distance = writer_options.get('text_distance', 5)

        # Set other writer options
        writer.module_width = writer_options.get('module_width', 0.2)
        writer.module_height = writer_options.get('module_height', 15.0)
        writer.quiet_zone = writer_options.get('quiet_zone', 6.5)
        writer.background = writer_options.get('background', 'white')
        writer.foreground = writer_options.get('foreground', 'black')
        writer.center_text = writer_options.get('center_text', True)

        # Generate barcode using the library's generate function
        buffer = BytesIO()
        generate(
            barcode_request.format,
            barcode_request.data,
            writer=writer,
            output=buffer,
            writer_options={'dpi': barcode_request.dpi} if barcode_request.dpi else None,
            text="" if not show_text else writer.text
        )

        # Process the generated image
        buffer.seek(0)
        img = PIL.Image.open(buffer)

        # Resize to requested dimensions
        img = img.resize((barcode_request.width, barcode_request.height), PIL.Image.Resampling.LANCZOS)

        # Save to new buffer
        try:
            with BytesIO() as output_buffer:
                img.save(
                    output_buffer,
                    format=writer_options.get('image_format', 'PNG'),
                    optimize=True
                )
                output_buffer.seek(0)
                return output_buffer.getvalue()
        finally:
            img.close()
            buffer.close()

    except BarcodeError as e:
        logger.error(f"Barcode generation error: {str(e)}")
        raise BarcodeGenerationError(str(e), "BarcodeError")
    except ValueError as e:
        logger.error(f"Value error in barcode generation: {str(e)}")
        raise BarcodeGenerationError(str(e), "ValueError")
    except Exception as e:
        logger.error(f"Unexpected error in barcode generation: {str(e)}")
        raise BarcodeGenerationError(f"An unexpected error occurred: {str(e)}", "UnexpectedError")

class BarcodeGenerator:
    """Simple barcode generator class for MCP WebSocket integration."""
    
    def generate_barcode(self, barcode_request: BarcodeRequest) -> Dict[str, any]:
        """
        Generate a barcode and return the image data.
        
        Args:
            barcode_request: The barcode generation request
            
        Returns:
            Dict containing image data and format information
        """
        try:
            # Set default writer options
            writer_options = {
                'image_format': 'PNG',
                'module_width': 0.2,
                'module_height': 15.0,
                'quiet_zone': 6.5,
                'background': 'white',
                'foreground': 'black',
                'font_size': 10,
                'text_distance': 5,
                'center_text': True
            }
            
            # Generate barcode image
            image_bytes = _generate_barcode_image_sync(barcode_request, writer_options)
            
            # Convert to base64 for JSON serialization
            import base64
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            return {
                'image_data': image_data,
                'format': 'png',
                'width': barcode_request.width,
                'height': barcode_request.height,
                'barcode_format': barcode_request.format
            }
            
        except Exception as e:
            logger.error(f"Error in BarcodeGenerator.generate_barcode: {e}", exc_info=True)
            raise