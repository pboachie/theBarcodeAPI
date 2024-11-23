# app/api/barcode.py

from app.barcode_generator import BarcodeGenerationError, generate_barcode_image
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from fastapi.param_functions import Form
from pydantic import ValidationError
from app.redis_manager import RedisManager
from app.rate_limiter import rate_limit
from app.dependencies import get_current_user, get_client_ip, get_redis_manager
from app.schemas import BarcodeRequest, UserData, BarcodeFormatEnum, BarcodeImageFormatEnum
from app.config import settings
from datetime import datetime, timedelta
import pytz
import asyncio.log as logging
from typing import Optional

logger = logging.getLogger(__name__)
rate_limit_val = 10000 if settings.ENVIRONMENT == 'development' else 50

router = APIRouter(prefix="/api", tags=["Barcodes"])

@router.get("/generate")
@rate_limit(times=rate_limit_val, interval=1, period="second")
async def generate_barcode(
    request: Request,
    data: str = Query(..., description="The data to encode in the barcode"),
    format: BarcodeFormatEnum = Query(..., description="Barcode format"),
    width: int = Query(default=200, ge=50, le=600),
    height: int = Query(default=100, ge=50, le=600),
    show_text: bool = Query(True, description="Whether to display text under the barcode"),
    text_content: Optional[str] = Query(None, description="Custom text to display under the barcode. If not provided and show_text is True, uses the encoded data"),
    module_width: Optional[float] = Query(None, description="Width of one barcode module in mm"),
    module_height: Optional[float] = Query(None, description="Height of the barcode modules in mm"),
    quiet_zone: Optional[float] = Query(None, description="Margin space around the barcode in mm"),
    font_size: Optional[int] = Query(None, description="Font size of the text under the barcode in pt"),
    text_distance: Optional[float] = Query(None, description="Distance between the barcode and the text under it in mm"),
    background: Optional[str] = Query(None, description="Background color of the barcode image"),
    foreground: Optional[str] = Query(None, description="Foreground and text color of the created barcode"),
    center_text: bool = Query(True, description="Center the text under the barcode"),
    image_format: BarcodeImageFormatEnum = Query(default=BarcodeImageFormatEnum.PNG),
    dpi: Optional[int] = Query(default=200, ge=130, le=600),
    add_checksum: Optional[bool] = Query(None),
    no_checksum: Optional[bool] = Query(None),
    guardbar: Optional[bool] = Query(None),
    redis_manager: RedisManager = Depends(get_redis_manager),
    current_user: UserData = Depends(get_current_user)
):
    """Generate a barcode image based on the provided parameters."""
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


        # Create options dictionary
        writer_options = {
            'module_width': module_width,
            'module_height': module_height,
            'quiet_zone': quiet_zone,
            'font_size': font_size if show_text else 0,
            'text_distance': text_distance if show_text else 0,
            'background': background,
            'foreground': foreground,
            'center_text': center_text,
            'image_format': image_format.value if image_format else 'PNG',
            'dpi': dpi
        }

        # Add text content to writer options if needed
        if show_text and text_content:
            writer_options['text_content'] = text_content

        # Filter out None values
        writer_options = {k: v for k, v in writer_options.items() if v is not None}

        # Get client IP
        ip_address = await get_client_ip(request)

        # Check remaining requests
        if current_user.remaining_requests <= 0:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

        try:
            barcode_image = await generate_barcode_image(barcode_request, writer_options)
        except BarcodeGenerationError as e:
            logger.error(f"Barcode generation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        # Update usage in Redis
        updated_user_data = await redis_manager.increment_usage(user_id=current_user.id, ip_address=ip_address)
        if not updated_user_data:
            logger.error("Error updating usage in Redis")
            raise HTTPException(
                status_code=500,
                detail="There was an error processing your request. Please try again."
            )

        # Parse image format and set media type
        image_format_str = barcode_request.image_format.value
        media_type = f"image/{image_format_str.lower()}"

        # Set response headers
        add_headers = {
            "X-Rate-Limit-Requests": str(updated_user_data.requests_today),
            "X-Rate-Limit-Remaining": str(updated_user_data.remaining_requests),
            "X-Rate-Limit-Reset": str(int((updated_user_data.last_reset + timedelta(days=1) - datetime.now(pytz.utc)).total_seconds())),
            "Server": f"TheBarcodeAPI/{settings.API_VERSION}",
            "Content-Type": media_type
        }

        return Response(
            content=barcode_image,
            media_type=media_type,
            headers=add_headers
        )

    except ValidationError as e:
        logger.error(f"Validation error: {e.errors()}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Validation error", "errors": e.errors()}
        )
    except BarcodeGenerationError as e:
        logger.error(f"Barcode generation error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={"message": e.message, "error_type": e.error_type}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )