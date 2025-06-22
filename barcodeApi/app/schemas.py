from pydantic import BaseModel, Field, field_serializer, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


class BatchPriority(str, Enum):
    """
    Priority levels for batch processing operations.

    Attributes:
        URGENT: Highest priority with 50ms target processing time
        HIGH: High priority with 500ms target processing time
        MEDIUM: Standard priority with 1s target processing time
        LOW: Low priority with 2s target processing time
    """
    URGENT = "URGENT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class BarcodeFormatEnum(str, Enum):
    """
    Comprehensive enumeration of supported barcode format types.

    This enum defines all barcode formats supported by theBarcodeAPI, each with
    specific requirements, constraints, and industry use cases.

    Format Categories:
    - **Linear Barcodes**: CODE128, CODE39, UPC, EAN series
    - **Publishing Standards**: ISBN, ISSN for books and serials
    - **Retail Standards**: UPC, EAN for product identification
    - **Logistics Standards**: ITF, GS1 for supply chain management
    - **Pharmaceutical**: PZN for German pharmaceutical products
    - **Regional Standards**: JAN for Japanese markets

    Data Length Requirements:
    - Most formats have strict length requirements (see BarcodeFormats for details)
    - Check digit calculation is automatic for applicable formats
    - Some formats support variable length data (CODE128, GS1-128)

    Performance Notes:
    - CODE128 and CODE39 offer fastest generation times
    - EAN/UPC formats include built-in validation
    - GS1 formats support rich data encoding
    """

    code128 = "code128"
    code39 = "code39"

    ean = "ean"
    ean13 = "ean13"
    ean14 = "ean14"
    ean8 = "ean8"

    gs1 = "gs1"
    gs1_128 = "gs1_128"
    gtin = "gtin"

    isbn = "isbn"
    isbn10 = "isbn10"
    isbn13 = "isbn13"
    issn = "issn"

    itf = "itf"
    jan = "jan"
    pzn = "pzn"

    upc = "upc"
    upca = "upca"

class BarcodeImageFormatEnum(str, Enum):
    """
    Supported image output formats for barcode generation.

    Each format offers different benefits:
    - **PNG**: Best for web use, supports transparency, lossless compression
    - **JPEG**: Smaller file sizes, good for high-resolution prints, lossy compression
    - **BMP**: Uncompressed format, largest file size, excellent quality
    - **GIF**: Legacy format, limited colors, supports animation
    - **TIFF**: Professional printing standard, excellent quality, lossless
    - **PCX**: Legacy format, rarely used in modern applications

    Recommended formats:
    - Web display: PNG (default)
    - Print applications: TIFF or PNG
    - Small file sizes: JPEG
    - Legacy systems: BMP
    """
    BMP = "BMP"
    GIF = "GIF"
    JPEG = "JPEG"
    PCX = "PCX"
    PNG = "PNG"
    TIFF = "TIFF"

class BarcodeFormat(BaseModel):
    """
    Detailed specification for a barcode format type.

    This model provides comprehensive information about each supported
    barcode format including technical specifications, options, and constraints.
    """
    name: str = Field(
        ...,
        description="Human-readable name of the barcode format",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "Code 128"}
    )
    code: str = Field(
        ...,
        description="Machine-readable code identifier for the format",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_]+$",
        json_schema_extra={"example": "code128"}
    )
    description: str = Field(
        ...,
        description="Detailed description of the format's purpose and characteristics",
        min_length=1,
        max_length=500,
        json_schema_extra={"example": "Variable-length linear barcode supporting full ASCII character set"}
    )
    options: Dict[str, str] = Field(
        default_factory=dict,
        description="Format-specific configuration options and their descriptions",
        json_schema_extra={
            "example": {
                "add_checksum": "Add checksum digit for error detection (default: True)",
                "text_below": "Display human-readable text below barcode (default: True)"
            }
        }
    )
    max_length: Optional[str] = Field(
        None,
        description="Maximum data length specification for this format",
        max_length=200,
        json_schema_extra={"example": "Variable (up to 48 characters in practice)"}
    )

class BarcodeFormats(BaseModel):
    formats: Dict[BarcodeFormatEnum, BarcodeFormat] = {
        BarcodeFormatEnum.code128: BarcodeFormat(
            name="Code 128",
            code="code128",
            description="Code 128 barcode implementation",
            max_length="Variable (up to 48 characters in practice, but it can encode much more depending on the character set)"
        ),
        BarcodeFormatEnum.code39: BarcodeFormat(
            name="Code 39",
            code="code39",
            description="A Code39 barcode implementation",
            options={
                "add_checksum": "Add the checksum to code or not (default: True)"
            },
            max_length="43 characters (may vary slightly based on the implementation)"
        ),
        BarcodeFormatEnum.ean: BarcodeFormat(
            name="EAN",
            code="ean",
            description="European Article Number",
            max_length="Typically 13 digits (EAN is the same as EAN-13): 13"
        ),
        BarcodeFormatEnum.ean13: BarcodeFormat(
            name="EAN-13",
            code="ean13",
            description="European Article Number 13 digits",
            options={
                "no_checksum": "Do not add checksum (default: False)",
                "guardbar": "Add guardbar (default: False)"
            },
            max_length="13 digits: 13"
        ),
        BarcodeFormatEnum.ean14: BarcodeFormat(
            name="EAN-14",
            code="ean14",
            description="European Article Number 14 digits",
            max_length="14 digits: 14"
        ),
        BarcodeFormatEnum.ean8: BarcodeFormat(
            name="EAN-8",
            code="ean8",
            description="European Article Number 8 digits",
            max_length="8 digits: 8"
        ),
        BarcodeFormatEnum.gs1: BarcodeFormat(
            name="GS1",
            code="gs1",
            description="GS1 barcode",
            max_length="Variable (depends on the specific GS1 application, usually up to 48 characters for GS1-128)"
        ),
        BarcodeFormatEnum.gs1_128: BarcodeFormat(
            name="GS1-128",
            code="gs1_128",
            description="GS1-128 barcode",
            max_length="Variable (up to 48 characters, depends on the application): 48"
        ),
        BarcodeFormatEnum.gtin: BarcodeFormat(
            name="GTIN",
            code="gtin",
            description="Global Trade Item Number",
            max_length="Either 8, 12, 13, or 14 digits (GTIN-8, GTIN-12, GTIN-13, GTIN-14): [8, 12, 13, 14]"
        ),
        BarcodeFormatEnum.isbn: BarcodeFormat(
            name="ISBN",
            code="isbn",
            description="International Standard Book Number",
            max_length="13 digits (for ISBN-13): 13"
        ),
        BarcodeFormatEnum.isbn10: BarcodeFormat(
            name="ISBN-10",
            code="isbn10",
            description="International Standard Book Number (10 digits)",
            max_length="10 digits: 10"
        ),
        BarcodeFormatEnum.isbn13: BarcodeFormat(
            name="ISBN-13",
            code="isbn13",
            description="International Standard Book Number (13 digits)",
            max_length="13 digits: 13"
        ),
        BarcodeFormatEnum.issn: BarcodeFormat(
            name="ISSN",
            code="issn",
            description="International Standard Serial Number",
            max_length="8 digits: 8"
        ),
        BarcodeFormatEnum.itf: BarcodeFormat(
            name="ITF",
            code="itf",
            description="Interleaved 2 of 5",
            max_length="14 digits (commonly used for GTIN-14): 14"
        ),
        BarcodeFormatEnum.jan: BarcodeFormat(
            name="JAN",
            code="jan",
            description="Japanese Article Number",
            max_length="13 digits (equivalent to EAN-13, used in Japan): 13"
        ),
        BarcodeFormatEnum.pzn: BarcodeFormat(
            name="PZN",
            code="pzn",
            description="Pharmazentralnummer",
            max_length="8 digits (Pharmazentralnummer used in Germany): 8"
        ),
        BarcodeFormatEnum.upc: BarcodeFormat(
            name="UPC",
            code="upc",
            description="Universal Product Code",
            max_length="12 digits (equivalent to UPC-A): 12"
        ),
        BarcodeFormatEnum.upca: BarcodeFormat(
            name="UPC-A",
            code="upca",
            description="Universal Product Code (Type A)",
            max_length="12 digits: 12"
        ),
    }

class BarcodeRequest(BaseModel):
    """
    Request model for barcode generation.

    Attributes:
        data: The content to be encoded in the barcode
        format: The barcode format type (see BarcodeFormatEnum)
        width: Barcode width in pixels (50-600)
        height: Barcode height in pixels (50-600)
        module_width: Width of a single barcode module in mm
        quiet_zone: Margin space around the barcode in mm
        text: Text to display under the barcode (will be empty if show_text is False)
    """
    data: str = Field(
        ...,
        description="Content to encode in the barcode",
        min_length=1,
        json_schema_extra={"example": "123456789012"}
    )
    format: BarcodeFormatEnum = Field(
        ...,
        description="Barcode format type",
        json_schema_extra={"example": "ean13"}
    )
    width: int = Field(
        default=200,
        ge=50,
        le=600,
        description="Width of the barcode image in pixels"
    )
    height: int = Field(
        default=100,
        ge=50,
        le=600,
        description="Height of the barcode image in pixels"
    )
    show_text: bool = Field(
        default=True,
        description="Whether to display text under the barcode"
    )
    text_content: Optional[str] = Field(
        None,
        description="Custom text to display under the barcode. If not provided, uses the encoded data"
    )
    module_width: Optional[float] = Field(
        None,
        description="Width of a single barcode module in mm"
    )
    module_height: Optional[float] = Field(
        None,
        description="Height of the barcode modules in mm"
    )
    quiet_zone: Optional[float] = Field(
        None,
        description="Margin space around the barcode in mm"
    )
    font_size: Optional[int] = Field(
        None,
        description="Font size of the text under the barcode in pt"
    )
    text_distance: Optional[float] = Field(
        None,
        description="Distance between the barcode and the text under it in mm"
    )
    background: Optional[str] = Field(
        None,
        description="Background color of the barcode image"
    )
    foreground: Optional[str] = Field(
        None,
        description="Foreground and text color of the barcode image"
    )
    center_text: bool = Field(
        default=True,
        description="Center the text under the barcode"
    )
    image_format: BarcodeImageFormatEnum = Field(
        default=BarcodeImageFormatEnum.PNG,
        description="Image file format for the barcode image"
    )
    dpi: int = Field(
        default=200,
        ge=130,
        le=600,
        description="DPI for the barcode image"
    )
    add_checksum: Optional[bool] = Field(
        None,
        description="Add the checksum to the barcode data"
    )
    no_checksum: Optional[bool] = Field(
        None,
        description="Do not add checksum to the barcode data"
    )
    guardbar: Optional[bool] = Field(
        None,
        description="Add guardbar to the barcode image"
    )

    def get_writer_options(self) -> Dict[str, Any]:
        """Get options for the barcode writer"""
        options = {
            'module_width': self.module_width,
            'module_height': self.module_height,
            'quiet_zone': self.quiet_zone,
            'background': self.background,
            'foreground': self.foreground,
            'center_text': self.center_text,
            'dpi': self.dpi,
            'image_format': self.image_format.value if self.image_format else 'PNG'
        }

        if not self.show_text:
            options['font_size'] = 0
            options['text_distance'] = 0
            options['text'] = ""
        else:
            options['font_size'] = self.font_size or 10
            options['text_distance'] = self.text_distance or 5
            options['text'] = self.text_content or self.data

        if self.add_checksum is not None:
            options['add_checksum'] = self.add_checksum
        if self.no_checksum is not None:
            options['no_checksum'] = self.no_checksum
        if self.guardbar is not None:
            options['guardbar'] = self.guardbar

        return {k: v for k, v in options.items() if v is not None}

    model_config = {
        "json_schema_extra": {
            "example": {
                "data": "123456789012",
                "format": "ean13",
                "width": 200,
                "height": 100,
                "show_text": True,
                "module_width": 0.2,
                "quiet_zone": 6.5,
                "image_format": "PNG",
                "dpi": 200,
                "background": "white",
                "foreground": "black"
            }
        }
    }

    @model_validator(mode='before')
    @classmethod
    def log_input(cls, values):
        return values

    @model_validator(mode='after')
    def validate_data_length(self):

        if self.data and self.format:
            if self.format == BarcodeFormatEnum.ean13 and len(self.data) != 12:
                raise ValueError(f"EAN-13 requires exactly 12 digits (13th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.ean8 and len(self.data) != 7:
                raise ValueError(f"EAN-8 requires exactly 7 digits (8th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.ean14 and len(self.data) != 13:
                raise ValueError(f"EAN-14 requires exactly 13 digits (14th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.upca and len(self.data) != 11:
                raise ValueError(f"UPC-A requires exactly 11 digits (12th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.isbn10 and len(self.data) != 9:
                raise ValueError(f"ISBN-10 requires exactly 9 digits (10th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.isbn13 and len(self.data) != 12:
                raise ValueError(f"ISBN-13 requires exactly 12 digits (13th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.issn and len(self.data) != 7:
                raise ValueError(f"ISSN requires exactly 7 digits (8th digit is the check digit). Got {len(self.data)} digits.")
            elif self.format == BarcodeFormatEnum.pzn and len(self.data) != 6:
                raise ValueError(f"PZN requires exactly 6 digits (7th digit is the check digit). Got {len(self.data)} digits.")
        else:
            logger.warning("Data or barcode format is None. Skipping length validation.")
        return self

    @property
    def max_length(self) -> Optional[str]:
        return BarcodeFormats().formats[self.format].max_length

class WriterOptions(BaseModel):
    """
    Configuration options for barcode writers.

    This model defines the standard parameters that control barcode appearance
    and formatting across different output formats.
    """
    module_width: float = Field(
        default=0.2,
        ge=0.1,
        le=5.0,
        description="The width of one barcode module in mm. Controls barcode thickness and readability."
    )
    module_height: float = Field(
        default=15.0,
        ge=5.0,
        le=50.0,
        description="The height of the barcode modules in mm. Affects scanning reliability."
    )
    quiet_zone: float = Field(
        default=6.5,
        ge=0.0,
        le=20.0,
        description="Distance on the left and right from the border to the first/last barcode module in mm"
    )
    font_size: int = Field(
        default=10,
        ge=6,
        le=24,
        description="Font size of the text under the barcode in pt"
    )
    text_distance: float = Field(
        default=5.0,
        ge=0.0,
        le=15.0,
        description="Distance between the barcode and the text under it in mm"
    )
    background: str = Field(
        default="white",
        max_length=50,
        description="The background color of the created barcode (CSS color name or hex code)"
    )
    foreground: str = Field(
        default="black",
        max_length=50,
        description="The foreground and text color of the created barcode (CSS color name or hex code)"
    )
    center_text: bool = Field(
        default=True,
        description="If true, the text is centered under the barcode; else left aligned"
    )

class SVGWriterOptions(WriterOptions):
    """
    SVG-specific writer options extending base WriterOptions.

    Provides additional configuration for SVG barcode output format.
    """
    compress: bool = Field(
        default=False,
        description="Boolean value to output a compressed SVG object (.svgz)"
    )

class ImageWriterOptions(WriterOptions):
    """
    Image-specific writer options extending base WriterOptions.

    Provides additional configuration for raster image formats (PNG, JPEG, BMP, etc.).
    """
    format: str = Field(
        default="PNG",
        description="The image file format (e.g., PNG, JPEG, BMP, TIFF, GIF)"
    )
    dpi: int = Field(
        default=200,
        ge=72,
        le=600,
        description="DPI (dots per inch) to calculate the image size in pixels. Higher DPI = better quality"
    )

class UsageResponse(BaseModel):
    """
    API usage statistics response model.

    Provides current usage information for rate limiting and quota management.
    """
    requests_today: int = Field(
        ...,
        ge=0,
        description="Number of API requests made today"
    )
    requests_limit: int = Field(
        ...,
        ge=0,
        description="Maximum number of requests allowed per day for this user tier"
    )
    remaining_requests: int = Field(
        ...,
        ge=0,
        description="Number of requests remaining in the current period"
    )
    reset_time: datetime = Field(
        ...,
        description="UTC datetime when the usage counters will reset"
    )

class UsageRequest(BaseModel):
    """
    Request model for tracking API usage.

    Used internally to log and track user API usage for rate limiting.
    """
    user_id: int = Field(
        ...,
        ge=1,
        description="Unique identifier for the user making the request"
    )
    ip_address: str = Field(
        ...,
        min_length=7,
        max_length=45,
        description="IP address of the client making the request"
    )

class TierEnum(str, Enum):
    """
    User subscription tier levels with different API rate limits.

    Tiers determine the daily request limits and feature access:
    - **basic**: Entry-level tier with limited daily requests
    - **standard**: Mid-tier with moderate request limits
    - **premium**: Highest tier with maximum request limits and priority support
    """
    basic = "basic"
    standard = "standard"
    premium = "premium"

class UserCreate(BaseModel):
    """
    Model for creating new user accounts.

    Used for user registration with validation for secure account creation.
    """
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique username (3-50 characters, alphanumeric, underscore, hyphen only)"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password for the account (minimum 8 characters)"
    )
    tier: TierEnum = Field(
        ...,
        description="User subscription tier determining API limits and features"
    )

class UserResponse(BaseModel):
    """
    Response model for user information.

    Provides user account details and current usage statistics.
    """
    id: str = Field(
        ...,
        description="Unique user identifier (nanoid format)"
    )
    username: str = Field(
        ...,
        description="User's chosen username"
    )
    ip_address: Optional[str] = Field(
        None,
        description="Last known IP address of the user"
    )
    tier: str = Field(
        ...,
        description="Current subscription tier (basic, standard, premium)"
    )
    remaining_requests: int = Field(
        ...,
        ge=0,
        description="Number of API requests remaining today"
    )
    requests_today: int = Field(
        ...,
        ge=0,
        description="Number of API requests made today"
    )
    last_request: Optional[datetime] = Field(
        None,
        description="Timestamp of the user's last API request"
    )
    last_reset: Optional[datetime] = Field(
        None,
        description="Timestamp when usage counters were last reset"
    )

class UsersResponse(BaseModel):
    """
    Response model for listing multiple users.

    Used for admin endpoints that return user collections.
    """
    users: List[UserResponse] = Field(
        ...,
        description="List of user objects with their details and usage statistics"
    )

class UserCreatedResponse(BaseModel):
    """
    Response model for successful user creation.

    Provides confirmation details when a new user account is successfully created.
    """
    message: str = Field(
        ...,
        description="Confirmation message indicating successful user creation"
    )
    user_id: str = Field(
        ...,
        description="Unique user identifier generated using nanoid format"
    )
    username: str = Field(
        ...,
        description="Username of the newly created user account"
    )
    tier: str = Field(
        ...,
        description="Assigned subscription tier for the new user"
    )

class UserData(BaseModel):
    """
    Comprehensive user data model for internal operations.

    This model handles user information with custom serialization for datetime fields
    and includes utility methods for JSON conversion.
    """
    id: str = Field(
        ...,
        description="Unique user identifier in nanoid format"
    )
    username: str = Field(
        ...,
        description="User's chosen username"
    )
    ip_address: Optional[str] = Field(
        None,
        description="Last known IP address of the user"
    )
    tier: str = Field(
        ...,
        description="Current subscription tier determining API limits"
    )
    remaining_requests: int = Field(
        ...,
        ge=0,
        description="Number of API requests remaining in current period"
    )
    requests_today: int = Field(
        ...,
        ge=0,
        description="Number of API requests made today"
    )
    last_request: Optional[datetime] = Field(
        None,
        description="Timestamp of the most recent API request"
    )
    last_reset: Optional[datetime] = Field(
        None,
        description="Timestamp when usage counters were last reset"
    )

    @field_serializer('last_request', 'last_reset')
    def serialize_datetime(cls, v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if v else None

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        },
        "from_attributes": True
        }

    @classmethod
    def parse_obj(cls, obj):
        if isinstance(obj, str):
            obj = json.loads(obj)
        for field in ['last_reset', 'last_request']:
            if isinstance(obj.get(field), str):
                obj[field] = datetime.fromisoformat(obj[field].rstrip('Z'))
        return super().model_validate(obj)

    def to_json(self):
        return json.dumps(self.model_dump(), default=str)

    @classmethod
    def from_json(cls, json_str):
        return cls.parse_obj(json.loads(json_str))

class HealthResponse(BaseModel):
    """
    Basic health check response model.

    Provides essential system status information for monitoring and alerting.
    """
    status: str = Field(
        ...,
        description="Overall system health status (healthy, degraded, unhealthy)"
    )
    version: str = Field(
        ...,
        description="Current API version"
    )
    database_status: str = Field(
        ...,
        description="Database connection status (connected, disconnected, error)"
    )
    redis_status: str = Field(
        ...,
        description="Redis cache connection status (connected, disconnected, error)"
    )

class RedisConnectionStats(BaseModel):
    """
    Redis connection statistics for detailed health monitoring.

    Provides metrics about Redis connection pool usage and client activity.
    """
    connected_clients: int = Field(
        ...,
        ge=0,
        description="Number of currently connected Redis clients"
    )
    blocked_clients: int = Field(
        ...,
        ge=0,
        description="Number of clients blocked on operations"
    )
    tracking_clients: int = Field(
        ...,
        ge=0,
        description="Number of clients being tracked for client-side caching"
    )
    total_connections: int = Field(
        ...,
        ge=0,
        description="Total number of connections made since Redis startup"
    )
    in_use_connections: int = Field(
        ...,
        ge=0,
        description="Number of connections currently in use by the connection pool"
    )

class DetailedHealthResponse(BaseModel):
    """
    Comprehensive health check response with system metrics.

    Provides detailed system information including resource usage,
    database status, and Redis connection statistics for monitoring dashboards.
    """
    status: str = Field(
        ...,
        description="Overall system health status (healthy, degraded, unhealthy)"
    )
    message: Optional[str] = Field(
        None,
        description="Additional status message or error details"
    )
    timestamp: Optional[str] = Field(
        None,
        description="ISO format timestamp when health check was performed"
    )
    cpu_usage: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Current CPU usage percentage (0-100)"
    )
    memory_usage: Optional[float] = Field(
        None,
        ge=0.0,
        description="Current memory usage in MB"
    )
    memory_total: Optional[float] = Field(
        None,
        ge=0.0,
        description="Total available memory in MB"
    )
    disk_usage: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Current disk usage percentage (0-100)"
    )
    database_status: Optional[str] = Field(
        None,
        description="Database connection status with additional details"
    )
    redis_status: Optional[str] = Field(
        None,
        description="Redis connection status with additional details"
    )
    redis_details: Optional[RedisConnectionStats] = Field(
        None,
        description="Detailed Redis connection pool statistics"
    )

class BatchProcessorResponse(BaseModel):
    """
    Response model for batch processing operations.

    Indicates the outcome of an asynchronous batch task, returning either
    the result of the operation or an error message if it failed.
    """
    result: Optional[Any] = Field(
        None,
        description="Result of the batch operation if successful"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the batch operation failed"
    )

class BarcodeGenerationError(Exception):
    """
    Custom exception for barcode generation failures.

    Used to signal errors during the barcode creation process, providing
    a specific error type for better error handling and logging.
    """
    def __init__(self, message: str, error_type: str):
        """
        Initializes the BarcodeGenerationError.

        Args:
            message: A human-readable error message describing the issue.
            error_type: A category or code for the type of error (e.g., 'validation', 'generation').
        """
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)

class SecurityScheme(BaseModel):
    """
    OpenAPI security scheme definition for JWT authentication.

    Defines the HTTP Bearer authentication method used for securing API endpoints.
    """
    type: str = Field(
        default="http",
        description="Authentication type (e.g., http, apiKey, oauth2)"
    )
    scheme: str = Field(
        default="bearer",
        description="Authentication scheme (e.g., bearer, basic)"
    )
    bearerFormat: str = Field(
        default="JWT",
        description="Format of the bearer token (e.g., JWT)"
    )


class JobStatusEnum(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class BulkFileMetadata(BaseModel):
    filename: str
    content_type: str
    item_count: int
    status: str
    message: Optional[str] = None


class BulkUploadResponse(BaseModel):
    job_id: str
    estimated_completion_time: Optional[str] = None
    files_processed: List[BulkFileMetadata]


class BarcodeResult(BaseModel):
    original_data: str
    output_filename: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    barcode_image_url: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatusEnum
    progress_percentage: float = Field(..., ge=0, le=100)
    results: Optional[List[BarcodeResult]] = None
    error_message: Optional[str] = None
    files: List[BulkFileMetadata]
