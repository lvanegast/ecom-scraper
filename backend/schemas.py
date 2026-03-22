"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ScraperSource(str, Enum):
    MERCADOLIBRE = "mercadolibre"
    AMAZON = "amazon"

# ============ Job Schemas ============
class JobCreate(BaseModel):
    """Schema for creating a new scraping job"""
    source: ScraperSource
    query_url: Optional[str] = None
    query_string: Optional[str] = None
    filter_mode: Optional[str] = "smart"

class JobResponse(BaseModel):
    """Schema for job response"""
    id: int
    source: ScraperSource
    query_url: Optional[str]
    query_string: Optional[str]
    status: JobStatus
    total_products: int
    found_count: int = 0
    saved_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    filter_mode: Optional[str] = "smart"
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str]

    class Config:
        from_attributes = True

# ============ Product Schemas ============
class PriceHistoryResponse(BaseModel):
    """Schema for price history"""
    id: int
    price: float
    scraped_at: datetime

    class Config:
        from_attributes = True

class ProductResponse(BaseModel):
    """Schema for product response"""
    id: int
    job_id: int
    title: str
    price: float
    original_price: Optional[float]
    discount_pct: Optional[float]
    currency: str
    stock_status: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    image_url: Optional[str]
    product_url: str
    scraped_at: datetime
    price_history: List[PriceHistoryResponse] = []

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    """Schema for creating a product (internal use)"""
    title: str
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = None
    currency: str = "USD"
    stock_status: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    image_url: Optional[str] = None
    product_url: str

# ============ Job Detail Schemas ============
class JobDetailResponse(JobResponse):
    """Extended job response with products"""
    products: List[ProductResponse] = []

# ============ WebSocket Messages ============
class LogMessage(BaseModel):
    """Schema for WebSocket log messages"""
    timestamp: datetime
    level: str  # "info", "success", "warning", "error"
    message: str
    job_id: int

class ScrapeUpdateMessage(BaseModel):
    """Schema for scrape progress update"""
    job_id: int
    status: JobStatus
    products_count: int
    current_product: Optional[str]
    message: str

# ============ Export Schemas ============
class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"

class ExportRequest(BaseModel):
    """Schema for export request"""
    job_id: int
    format: ExportFormat = ExportFormat.CSV
