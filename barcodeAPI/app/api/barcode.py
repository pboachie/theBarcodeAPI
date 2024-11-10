# app/api/barcode.py

from app.barcode_generator import BarcodeGenerationError, generate_barcode_image
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from pydantic import ValidationError
from app.redis_manager import RedisManager
from app.redis import get_redis_manager
from app.rate_limiter import rate_limit
from app.dependencies import get_current_user, get_client_ip
from app.schemas import BarcodeRequest, UserData, BarcodeFormatEnum, BarcodeImageFormatEnum
from app.config import settings
from datetime import datetime, timedelta
import pytz
import logging
from typing import Optional

logger = logging.getLogger(__name__)
rate_limit_val = 10000 if settings.ENVIRONMENT == 'development' else 50

router = APIRouter(prefix="/api", tags=["Barcodes"])

@router.get("/generate")
async def generate_barcode(
    request: Request,
    data: str = Query(..., description="The data to encode in the barcode"),
    format: BarcodeFormatEnum = Query(..., description="Barcode format"),
    width: int = Query(default=200, ge=50, le=600),
    height: int = Query(default=100, ge=50, le=600),
    module_width: Optional[float] = Query(None, description="The width of one barcode module in mm"),
    module_height: Optional[float] = Query(None, description="The height of the barcode modules in mm"),
    quiet_zone: Optional[float] = Query(None, description="Distance on the left and right from the border to the first/last barcode module in mm"),
    font_size: Optional[int] = Query(None, description="Font size of the text under the barcode in pt"),
    text_distance: Optional[float] = Query(None, description="Distance between the barcode and the text under it in mm"),
    background: Optional[str] = Query(None, description="The background color of the created barcode"),
    foreground: Optional[str] = Query(None, description="The foreground and text color of the created barcode"),
    center_text: Optional[bool] = Query(True, description="If true, the text is centered under the barcode; else left aligned"),
    image_format: BarcodeImageFormatEnum = Query(default=BarcodeImageFormatEnum.PNG, description="The image file format"),
    dpi: Optional[int] = Query(default=200, ge=130, le=600, description="DPI to calculate the image size in pixels"),
    add_checksum: Optional[bool] = Query(None, description="Add the checksum to code or not (for Code 39)"),
    no_checksum: Optional[bool] = Query(None, description="Do not add checksum (for EAN-13)"),
    guardbar: Optional[bool] = Query(None, description="Add guardbar (for EAN-13)"),
    redis_manager: RedisManager = Depends(get_redis_manager),
    current_user: UserData = Depends(get_current_user),
    _: None = Depends(rate_limit(times=rate_limit_val, interval=1, period="second"))
):
    """Generate a barcode image based on the provided parameters.

    This endpoint creates a barcode image and returns it as a PNG.
    Usage is tracked and limited based on the user's authentication status and tier.

    - Authenticated users: Limits are based on their account tier.
    - Unauthenticated users: A default limit is applied based on their IP, etc.

    Rate limited to 1000 requests per second.
    """
    try:
        barcode_request = BarcodeRequest(
            data=data,
            format=format,
            width=width,
            height=height,
            module_width=module_width,
            module_height=module_height,
            quiet_zone=quiet_zone,
            font_size=font_size,
            text_distance=text_distance,
            background=background,
            foreground=foreground,
            center_text=center_text,
            image_format=image_format,
            dpi=dpi,
            add_checksum=add_checksum,
            no_checksum=no_checksum,
            guardbar=guardbar
        )

        # Get client IP
        ip_address = await get_client_ip(request)

        if isinstance(current_user, tuple):
            user_id, _ = current_user

            user_data = UserData(
                id=user_id if user_id else -1,
                username=f"ip:{ip_address}",
                ip_address=ip_address,
                tier="unauthenticated",
                remaining_requests=settings.RateLimit.get_limit("unauthenticated"),
                requests_today=0,
                last_reset=datetime.now(pytz.utc)
            )
        else:
            user_data = current_user

        # Check remaining requests
        if user_data.remaining_requests <= 0:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

        # Get writer options and generate barcode
        writer_options = barcode_request.get_writer_options()
        try:
            barcode_image = await generate_barcode_image(barcode_request, writer_options)
        except BarcodeGenerationError as e:
            logger.error(f"Barcode generation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        # Update usage in Redis
        updated_user_data = await redis_manager.increment_usage(user_id=user_data.id, ip_address=ip_address)
        if not updated_user_data:
            logger.error("Error updating usage in Redis")
            raise HTTPException(
                status_code=500,
                detail="There was an error with your API Key. Please try again or contact support."
            )

        # Parse image format and set media type
        image_format_str = barcode_request.image_format.value
        media_type = f"image/{image_format_str.lower()}"

        # Ensure last_reset has timezone info
        if updated_user_data.last_reset.tzinfo is None:
            updated_user_data.last_reset = updated_user_data.last_reset.replace(tzinfo=pytz.utc)

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
        logger.error(f"Unexpected error generating barcode: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the barcode"
        )