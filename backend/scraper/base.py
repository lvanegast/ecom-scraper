"""
Base scraper class with shared functionality
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
import logging
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ScrapedProduct:
    """Dataclass representing a scraped product"""
    title: str
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = None
    currency: str = "USD"
    stock_status: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    image_url: Optional[str] = None
    product_url: str = ""

class BaseScraper(ABC):
    """
    Abstract base scraper class
    All site-specific scrapers inherit from this
    """
    
    def __init__(self, log_callback: Optional[Callable] = None):
        """
        Initialize scraper
        
        Args:
            log_callback: Async function to send logs to WebSocket
        """
        self.log_callback = log_callback
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def send_log(self, message: str, level: str = "info"):
        """
        Send log message via callback (WebSocket)
        
        Args:
            message: Log message
            level: Log level (info, success, warning, error)
        """
        if self.log_callback:
            try:
                await self.log_callback(message, level)
            except Exception as e:
                self.logger.error(f"Error sending log: {e}")
        
        # Also log to standard logger
        getattr(self.logger, level, self.logger.info)(message)
    
    @abstractmethod
    async def scrape(self, query: str) -> List[ScrapedProduct]:
        """
        Main scraping method - must be implemented by subclasses
        
        Args:
            query: Search query or URL
            
        Returns:
            List of ScrapedProduct objects
        """
        pass
    
    def calculate_discount(self, original_price: float, current_price: float) -> float:
        """Calculate discount percentage"""
        if original_price <= 0:
            return 0.0
        return round(((original_price - current_price) / original_price) * 100, 2)
    
    def normalize_price(self, price_str: str) -> float:
        """
        Parse price string and return float
        Handles various formats: "$100", "100.50", "100,50", etc
        """
        import re
        # Remove currency symbols and whitespace, keep digits/separators
        price_str = re.sub(r'[^\d.,]', '', str(price_str).strip())
        if not price_str:
            return 0.0

        # If both separators exist, assume the last one is decimal
        if ',' in price_str and '.' in price_str:
            if price_str.rfind(',') > price_str.rfind('.'):
                decimal_sep = ','
                thousands_sep = '.'
            else:
                decimal_sep = '.'
                thousands_sep = ','
            price_str = price_str.replace(thousands_sep, '')
            price_str = price_str.replace(decimal_sep, '.')
        else:
            # Only one separator or none
            sep = ',' if ',' in price_str else '.' if '.' in price_str else None
            if sep:
                parts = price_str.split(sep)
                if len(parts) > 2:
                    # Treat all separators as thousands
                    price_str = ''.join(parts)
                else:
                    # If exactly 3 digits after sep, likely thousands separator
                    if len(parts[1]) == 3:
                        price_str = ''.join(parts)
                    else:
                        price_str = price_str.replace(',', '.')

        try:
            return float(price_str)
        except ValueError:
            return 0.0
    
    async def close(self):
        """Cleanup resources (e.g., browser, session)"""
        pass
