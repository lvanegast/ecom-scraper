"""
SQLAlchemy ORM models for EcomScraper
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Text, Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from database import Base

class JobStatus(str, enum.Enum):
    """Enum for job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ScraperSource(str, enum.Enum):
    """Enum for scraper source"""
    MERCADOLIBRE = "mercadolibre"
    AMAZON = "amazon"

class Job(Base):
    """
    Scraping job model
    tracks jobs initiated by users
    """
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(SQLEnum(ScraperSource), nullable=False)
    # Either query_url or query_string will be provided depending on job type
    query_url = Column(String, nullable=True)
    query_string = Column(String, nullable=True)  # For keyword searches
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    total_products = Column(Integer, default=0)
    found_count = Column(Integer, default=0)
    saved_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    filter_mode = Column(String, default="smart")
    error_message = Column(Text, nullable=True)
    
    # Relationships
    products = relationship("Product", back_populates="job", cascade="all, delete-orphan")

class Product(Base):
    """
    Product data extracted from scraping
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    discount_pct = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    stock_status = Column(String, nullable=True)  # "In Stock", "Out of Stock", etc
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    image_url = Column(String, nullable=True)
    product_url = Column(String, nullable=False, index=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    job = relationship("Job", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_products_job_url", "job_id", "product_url"),
    )

class PriceHistory(Base):
    """
    Historical price tracking for each product
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    product = relationship("Product", back_populates="price_history")
