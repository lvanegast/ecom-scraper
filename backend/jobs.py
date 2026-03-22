"""
Background job management for scraping tasks
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models import Job, Product, PriceHistory, JobStatus, ScraperSource
from schemas import ProductCreate
from scraper.mercadolibre import MercadoLibreScraper
from scraper.amazon import AmazonScraper

logger = logging.getLogger(__name__)

class ScrapingJobManager:
    """Manages scraping job lifecycle"""
    
    def __init__(self, db_session: AsyncSession, log_callback: Optional[Callable] = None):
        self.db = db_session
        self.log_callback = log_callback
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def get_scraper(self, source: ScraperSource, filter_mode: str = "smart"):
        """Get scraper instance based on source"""
        if source == ScraperSource.MERCADOLIBRE:
            return MercadoLibreScraper(log_callback=self.log_callback)
        elif source == ScraperSource.AMAZON:
            return AmazonScraper(log_callback=self.log_callback, filter_mode=filter_mode)
        else:
            raise ValueError(f"Unknown scraper source: {source}")
    
    async def execute_job(self, job_id: int) -> bool:
        """
        Execute a scraping job
        
        Args:
            job_id: Job ID to execute
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get job from database
            result = await self.db.execute(select(Job).where(Job.id == job_id))
            job = result.scalars().first()
            
            if not job:
                self.logger.error(f"Job {job_id} not found")
                return False
            
            # Update job status to RUNNING
            await self.db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.RUNNING)
            )
            await self.db.commit()
            
            # Log start
            query = job.query_string or job.query_url
            await self._log(f"🚀 Iniciando job de scraping: {query}", "info")
            
            # Get scraper
            scraper = await self.get_scraper(job.source, getattr(job, "filter_mode", "smart"))
            
            try:
                # Execute scraping
                scraped_products = await scraper.scrape(query)
                
                # Save products to database
                saved_count, duplicate_count, error_count = await self._save_products(
                    job_id, scraped_products
                )
                
                # Update job status to COMPLETED
                await self.db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status=JobStatus.COMPLETED,
                        total_products=saved_count,
                        found_count=len(scraped_products),
                        saved_count=saved_count,
                        duplicate_count=duplicate_count,
                        error_count=error_count,
                    )
                )
                await self.db.commit()
                
                await self._log(
                    "✅ Job completado: "
                    f"{saved_count} guardados, {duplicate_count} duplicados, "
                    f"{error_count} errores (de {len(scraped_products)} encontrados)",
                    "success"
                )
                
                return True
                
            finally:
                await scraper.close()
                
        except Exception as e:
            error_msg = f"❌ Error en job {job_id}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            await self._log(error_msg, "error")
            
            # Update job status to FAILED
            try:
                await self.db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status=JobStatus.FAILED,
                        error_message=str(e)
                    )
                )
                await self.db.commit()
            except Exception as db_error:
                self.logger.error(f"Error updating job status: {db_error}")
            
            return False
    
    async def _save_products(self, job_id: int, scraped_products: list):
        """Save scraped products to database

        Returns:
            (saved_count, duplicate_count, error_count)
        """
        saved_count = 0
        duplicate_count = 0
        error_count = 0
        for scraped_product in scraped_products:
            try:
                if not scraped_product.product_url or not scraped_product.title:
                    error_count += 1
                    continue
                # Check if product already exists
                result = await self.db.execute(
                    select(Product).where(
                        Product.product_url == scraped_product.product_url,
                        Product.job_id == job_id
                    )
                )
                existing_product = result.scalars().first()
                
                if existing_product:
                    duplicate_count += 1
                    # Update price history if price changed
                    result = await self.db.execute(
                        select(PriceHistory)
                        .where(PriceHistory.product_id == existing_product.id)
                        .order_by(PriceHistory.id.desc())
                        .limit(1)
                    )
                    last_price_record = result.scalars().first()
                    
                    if (not last_price_record or 
                        last_price_record.price != scraped_product.price):
                        new_price_history = PriceHistory(
                            product_id=existing_product.id,
                            price=scraped_product.price
                        )
                        self.db.add(new_price_history)
                else:
                    # Create new product
                    new_product = Product(
                        job_id=job_id,
                        title=scraped_product.title,
                        price=scraped_product.price,
                        original_price=scraped_product.original_price,
                        discount_pct=scraped_product.discount_pct,
                        currency=scraped_product.currency,
                        stock_status=scraped_product.stock_status,
                        rating=scraped_product.rating,
                        review_count=scraped_product.review_count,
                        image_url=scraped_product.image_url,
                        product_url=scraped_product.product_url,
                    )
                    self.db.add(new_product)
                    await self.db.flush()  # Get the ID
                    
                    # Create initial price history
                    price_history = PriceHistory(
                        product_id=new_product.id,
                        price=scraped_product.price
                    )
                    self.db.add(price_history)
                    saved_count += 1
                
                await self.db.commit()
                
            except Exception as e:
                self.logger.error(
                    f"Error saving product {scraped_product.title}: {e}",
                    exc_info=True
                )
                await self.db.rollback()
                error_count += 1

        return saved_count, duplicate_count, error_count
    
    async def _log(self, message: str, level: str = "info"):
        """Send log message"""
        if self.log_callback:
            try:
                await self.log_callback(message, level)
            except Exception as e:
                self.logger.error(f"Error in log callback: {e}")
