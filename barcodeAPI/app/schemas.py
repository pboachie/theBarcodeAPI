# app/schemas.py
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

class BatchPriority(Enum):
    URGENT = "urgent" # 50ms
    HIGH = "high" # 500ms
    MEDIUM = "medium" # 1s
    LOW = "low" # 2s

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class BarcodeFormatEnum(str, Enum):
    code128 = "code128" # Default
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
    BMP = "BMP"
    GIF = "GIF"
    JPEG = "JPEG"
    # MSP = "MSP"
    PCX = "PCX"
    PNG = "PNG"
    TIFF = "TIFF"
    # XBM = "XBM"

class BarcodeFormat(BaseModel):
    name: str
    code: str
    description: str
    options: Dict[str, str] = {}
    max_length: Optional[str] = None

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
    data: str = Field(..., description="The data to encode in the barcode")
    format: BarcodeFormatEnum = Field(..., description="Barcode format")
    width: int = Field(default=200, ge=50, le=600)
    height: int = Field(default=100, ge=50, le=600)
    module_width: Optional[float] = Field(None, description="The width of one barcode module in mm")
    module_height: Optional[float] = Field(None, description="The height of the barcode modules in mm")
    quiet_zone: Optional[float] = Field(None, description="Distance on the left and right from the border to the first/last barcode module in mm")
    font_size: Optional[int] = Field(None, description="Font size of the text under the barcode in pt")
    text_distance: Optional[float] = Field(None, description="Distance between the barcode and the text under it in mm")
    background: Optional[str] = Field(None, description="The background color of the created barcode")
    foreground: Optional[str] = Field(None, description="The foreground and text color of the created barcode")
    center_text: Optional[bool] = Field(default=True, description="If true, the text is centered under the barcode; else left aligned")
    image_format: BarcodeImageFormatEnum = Field(default=BarcodeImageFormatEnum.PNG, description="The image file format (e.g., PNG, JPEG, BMP)")
    dpi: Optional[int] = Field(default=300, ge=130, le=600, description="DPI to calculate the image size in pixels")
    add_checksum: Optional[bool] = Field(None, description="Add the checksum to code or not (for Code 39)")
    no_checksum: Optional[bool] = Field(None, description="Do not add checksum (for EAN-13)")
    guardbar: Optional[bool] = Field(None, description="Add guardbar (for EAN-13)")

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

    def get_writer_options(self) -> Dict[str, any]:
        options = {}
        for field in self.model_fields:
            if field not in ['data', 'format', 'width', 'height'] and getattr(self, field) is not None:
                options[field] = getattr(self, field)
        return options

    @property
    def max_length(self) -> Optional[str]:
        return BarcodeFormats().formats[self.format].max_length

class WriterOptions(BaseModel):
    module_width: float = Field(default=0.2, description="The width of one barcode module in mm")
    module_height: float = Field(default=15.0, description="The height of the barcode modules in mm")
    quiet_zone: float = Field(default=6.5, description="Distance on the left and right from the border to the first/last barcode module in mm")
    # font_path: str = Field(default="DejaVuSansMono", description="Path to the font file to be used")
    font_size: int = Field(default=10, description="Font size of the text under the barcode in pt")
    text_distance: float = Field(default=5.0, description="Distance between the barcode and the text under it in mm")
    background: str = Field(default="white", description="The background color of the created barcode")
    foreground: str = Field(default="black", description="The foreground and text color of the created barcode")
    center_text: bool = Field(default=True, description="If true, the text is centered under the barcode; else left aligned")

class SVGWriterOptions(WriterOptions):
    compress: bool = Field(default=False, description="Boolean value to output a compressed SVG object (.svgz)")

class ImageWriterOptions(WriterOptions):
    format: str = Field(default="PNG", description="The image file format (e.g., PNG, JPEG, BMP)")
    dpi: int = Field(default=200, description="DPI to calculate the image size in pixels")

class UsageResponse(BaseModel):
    requests_today: int
    requests_limit: int
    remaining_requests: int

class UsageRequest(BaseModel):
    user_id: int
    ip_address: str

class TierEnum(str, Enum):
    basic = "basic"
    standard = "standard"
    premium = "premium"

class UserCreate(BaseModel):
    username: str
    password: str
    tier: TierEnum = Field(..., description="User tier: basic, standard, or premium")

class UserResponse(BaseModel):
    id: int
    username: str
    tier: str

class UsersResponse(BaseModel):
    users: List[UserResponse]

class UserCreatedResponse(BaseModel):
    message: str
    user_id: int
    username: str
    tier: str

class UserData(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    tier: str
    remaining_requests: int
    requests_today: int
    last_reset: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        from_attributes = True

    @classmethod
    def parse_obj(cls, obj):
        if isinstance(obj, str):
            obj = json.loads(obj)
        if isinstance(obj.get('last_reset'), str):
            obj['last_reset'] = datetime.fromisoformat(obj['last_reset'].rstrip('Z'))
        return super().parse_obj(obj)

    def to_json(self):
        return json.dumps(self.dict(), default=str)

    @classmethod
    def from_json(cls, json_str):
        return cls.parse_obj(json.loads(json_str))


class HealthResponse(BaseModel):
    status: str
    version: str
    database_status: str
    redis_status: str

class RedisConnectionStats(BaseModel):
    connected_clients: int
    blocked_clients: int
    tracking_clients: int

class DetailedHealthResponse(BaseModel):
    status: str
    message: Optional[str] = None
    timestamp: Optional[str] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    memory_total: Optional[float] = None
    disk_usage: Optional[float] = None
    database_status: Optional[str] = None
    redis_status: Optional[str] = None
    redis_details: Optional[RedisConnectionStats] = None

