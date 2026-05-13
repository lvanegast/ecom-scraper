"""
EcomScraper - FastAPI main application
Real-time ecommerce scraping with WebSocket streaming
"""
import asyncio
import logging
import csv
import json
import os
from datetime import datetime
from typing import Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from sqlalchemy.orm import selectinload
import httpx
import uvicorn

from database import get_db, engine, Base
from models import Job, JobStatus, ScraperSource, Product, PriceHistory
from schemas import (
    JobCreate, JobResponse, JobDetailResponse, ProductResponse,
    ExportFormat, ExportRequest
)
from jobs import ScrapingJobManager
from compare import extract_features, best_match_for

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ WebSocket Manager ============
class ConnectionManager:
    """Manage WebSocket connections for log streaming"""
    
    def __init__(self):
        self.active_connections: dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: int):
        """Accept and register WebSocket connection"""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)
    
    async def disconnect(self, websocket: WebSocket, job_id: int):
        """Disconnect WebSocket"""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
    
    async def broadcast(self, job_id: int, message: dict):
        """Broadcast log message to all connected clients for a job"""
        if job_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.add(connection)
            
            # Clean up disconnected
            for conn in disconnected:
                await self.disconnect(conn, job_id)

manager = ConnectionManager()

# ============ Lifespan Events ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown"""
    # Startup
    logger.info("🚀 Starting EcomScraper...")
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✓ Database initialized")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down EcomScraper...")
    await engine.dispose()

# ============ FastAPI App ============
app = FastAPI(
    title="EcomScraper API",
    description="Real-time ecommerce scraping with WebSocket streaming",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

def get_allowed_origins() -> list[str]:
    """Read allowed CORS origins from env, with sensible local defaults."""
    configured_origins = os.getenv("ALLOWED_ORIGINS")
    if configured_origins:
        return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]

    return [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
    ]


allowed_origins = get_allowed_origins()
allow_credentials = "*" not in allowed_origins

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Helper Functions ============
async def create_log_callback(job_id: int):
    """Create log callback function for scraper"""
    async def log_callback(message: str, level: str = "info"):
        await manager.broadcast(job_id, {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "job_id": job_id
        })
    return log_callback

# ============ API Routes ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "EcomScraper"}

@app.get("/api/docs", include_in_schema=False)
async def scalar_docs():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>EcomScraper API Docs</title>
        <meta charset="utf-8" />
    </head>
    <body>
        <script
            id="api-reference"
            data-url="/api/openapi.json"
            data-configuration='{"theme": "purple", "layout": "modern"}'
        ></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
    </body>
    </html>
    """)

@app.get("/api/openapi.json", include_in_schema=False)
async def openapi_json():
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

@app.get("/api/my-ip")
async def get_my_ip():
    """Verifica la IP publica desde donde sale el trafico del backend"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get("https://api.ipify.org?format=json")
        data = response.json()
        return {
            "outbound_ip": data.get("ip"),
            "note": "Esta IP debe coincidir con la Elastic IP del NAT Gateway"
        }

# ============ Job Management Endpoints ============

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    job_input: JobCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scraping job
    
    Args:
        job_input: Job creation data (source, query_url or query_string)
        db: Database session
        
    Returns:
        Created job with initial status
    """
    try:
        if not job_input.query_url and not job_input.query_string:
            raise HTTPException(
                status_code=400,
                detail="Either query_url or query_string is required"
            )
        
        # Validate filter mode
        allowed_filters = {"smart", "strict", "off"}
        if job_input.filter_mode and job_input.filter_mode not in allowed_filters:
            raise HTTPException(
                status_code=400,
                detail="filter_mode must be one of: smart, strict, off"
            )

        # Create job
        new_job = Job(
            source=job_input.source,
            query_url=job_input.query_url,
            query_string=job_input.query_string,
            status=JobStatus.PENDING,
            filter_mode=job_input.filter_mode or "smart",
        )
        
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)
        
        logger.info(f"Created job {new_job.id}: {job_input.source}")
        
        # Launch background scraping task
        asyncio.create_task(
            _execute_scraping_task(new_job.id)
        )
        
        return new_job
        
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs", response_model=list[JobResponse])
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: JobStatus = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    List all scraping jobs
    
    Args:
        skip: Pagination offset
        limit: Pagination limit
        status: Filter by job status
        db: Database session
        
    Returns:
        List of jobs
    """
    query = select(Job).order_by(desc(Job.created_at))
    
    if status:
        query = query.where(Job.status == status)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return jobs

@app.get("/api/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed job information with products
    
    Args:
        job_id: Job ID
        db: Database session
        
    Returns:
        Job with associated products and price history
    """
    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.products).selectinload(Product.price_history)
        )
        .where(Job.id == job_id)
    )
    job = result.scalars().first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job

# ============ Product Endpoints ============

@app.get("/api/products/{job_id}", response_model=list[ProductResponse])
async def get_job_products(
    job_id: int,
    sort_by: str = Query("scraped_at", pattern="^(price|rating|scraped_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get products for a job with sorting
    
    Args:
        job_id: Job ID
        sort_by: Sort field (price, rating, scraped_at)
        sort_order: Sort direction (asc, desc)
        db: Database session
        
    Returns:
        List of products
    """
    # Verify job exists
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalars().first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build query
    query = (
        select(Product)
        .options(selectinload(Product.price_history))
        .where(Product.job_id == job_id)
    )
    
    # Apply sorting
    if sort_by == "price":
        sort_col = Product.price
    elif sort_by == "rating":
        sort_col = Product.rating
    else:
        sort_col = Product.scraped_at
    
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
    
    result = await db.execute(query)
    products = result.scalars().all()
    
    return products

@app.get("/api/products/{product_id}/price-history")
async def get_price_history(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get price history for a product"""
    
    # Verify product exists
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get price history
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.scraped_at.asc())
    )
    history = result.scalars().all()
    
    return {
        "product_id": product_id,
        "title": product.title,
        "history": [
            {
                "price": h.price,
                "scraped_at": h.scraped_at.isoformat()
            }
            for h in history
        ]
    }

# ============ Compare Endpoints ============

@app.get("/api/compare/latest")
async def compare_latest_jobs(
    threshold: float = Query(0.35, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db)
):
    """
    Compare latest completed MercadoLibre vs Amazon jobs.
    Returns top_k matches per MercadoLibre product.
    """
    # Latest completed jobs per source
    ml_result = await db.execute(
        select(Job)
        .where(Job.source == ScraperSource.MERCADOLIBRE, Job.status == JobStatus.COMPLETED)
        .order_by(desc(Job.created_at))
        .limit(1)
    )
    amz_result = await db.execute(
        select(Job)
        .where(Job.source == ScraperSource.AMAZON, Job.status == JobStatus.COMPLETED)
        .order_by(desc(Job.created_at))
        .limit(1)
    )

    ml_job = ml_result.scalars().first()
    amz_job = amz_result.scalars().first()

    missing = []
    if not ml_job:
        missing.append("mercadolibre")
    if not amz_job:
        missing.append("amazon")
    if missing:
        return {
            "ml_job_id": ml_job.id if ml_job else None,
            "amz_job_id": amz_job.id if amz_job else None,
            "threshold": threshold,
            "missing_sources": missing,
            "results": [],
            "message": "Se requieren jobs completados de ambas plataformas para comparar",
        }

    ml_products_result = await db.execute(
        select(Product).where(Product.job_id == ml_job.id)
    )
    amz_products_result = await db.execute(
        select(Product).where(Product.job_id == amz_job.id)
    )

    ml_products = ml_products_result.scalars().all()
    amz_products = amz_products_result.scalars().all()

    # Precompute Amazon features
    amz_features = {
        p.id: extract_features(p.title or "")
        for p in amz_products
    }

    matches = []
    for ml in ml_products:
        ml_feats = extract_features(ml.title or "")
        best_id, best_score = best_match_for(ml_feats, amz_features)

        if best_id is None:
            matches.append({
                "ml_product": _serialize_product(ml),
                "amz_product": None,
                "score": best_score,
                "price_diff": None,
                "is_confident": False,
            })
            continue

        amz = next((p for p in amz_products if p.id == best_id), None)
        price_diff = None
        if amz and ml.price and amz.price:
            price_diff = round(amz.price - ml.price, 2)

        matches.append({
            "ml_product": _serialize_product(ml),
            "amz_product": _serialize_product(amz) if amz else None,
            "score": best_score,
            "price_diff": price_diff,
            "is_confident": best_score >= threshold,
        })

    return {
        "ml_job_id": ml_job.id,
        "amz_job_id": amz_job.id,
        "threshold": threshold,
        "results": matches,
    }


def _serialize_product(product: Product | None) -> dict | None:
    if product is None:
        return None
    return {
        "id": product.id,
        "job_id": product.job_id,
        "title": product.title,
        "price": product.price,
        "currency": product.currency,
        "stock_status": product.stock_status,
        "rating": product.rating,
        "review_count": product.review_count,
        "image_url": product.image_url,
        "product_url": product.product_url,
    }

# ============ Export Endpoints ============

@app.post("/api/export")
async def export_data(
    export_request: ExportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Export job results to CSV or JSON
    
    Args:
        export_request: Export configuration (job_id, format)
        db: Database session
        
    Returns:
        File download
    """
    # Verify job exists
    result = await db.execute(
        select(Job).where(Job.id == export_request.job_id)
    )
    job = result.scalars().first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get products
    result = await db.execute(
        select(Product).where(Product.job_id == export_request.job_id)
    )
    products = result.scalars().all()
    
    if export_request.format == ExportFormat.CSV:
        return _generate_csv_export(job, products)
    else:
        return _generate_json_export(job, products)

def _generate_csv_export(job: Job, products: list):
    """Generate CSV export"""
    import io
    
    output = io.StringIO()
    
    if not products:
        # Empty CSV with headers
        writer = csv.writer(output)
        writer.writerow([
            "Title", "Price", "Original Price", "Discount %",
            "Currency", "Rating", "Reviews", "Stock", "Product URL"
        ])
    else:
        writer = csv.writer(output)
        writer.writerow([
            "Title", "Price", "Original Price", "Discount %",
            "Currency", "Rating", "Reviews", "Stock", "Product URL"
        ])
        
        for product in products:
            writer.writerow([
                product.title,
                product.price,
                product.original_price or "",
                product.discount_pct or "",
                product.currency,
                product.rating or "",
                product.review_count or "",
                product.stock_status or "",
                product.product_url,
            ])
    
    content = output.getvalue()
    
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=products_{job.id}.csv"}
    )

def _generate_json_export(job: Job, products: list):
    """Generate JSON export"""
    data = {
        "job": {
            "id": job.id,
            "source": job.source.value,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "total_products": len(products),
        },
        "products": [
            {
                "title": p.title,
                "price": p.price,
                "original_price": p.original_price,
                "discount_pct": p.discount_pct,
                "currency": p.currency,
                "rating": p.rating,
                "review_count": p.review_count,
                "stock_status": p.stock_status,
                "product_url": p.product_url,
                "scraped_at": p.scraped_at.isoformat(),
            }
            for p in products
        ]
    }
    
    content = json.dumps(data, indent=2)
    
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=products_{job.id}.json"}
    )

# ============ WebSocket Endpoints ============

@app.websocket("/ws/logs/{job_id}")
async def websocket_logs(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for real-time log streaming
    
    Connects client to job logs stream
    """
    await manager.connect(websocket, job_id)
    
    try:
        logger.info(f"WebSocket connected for job {job_id}")
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Optional: handle incoming messages (e.g., commands)
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket, job_id)
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        await manager.disconnect(websocket, job_id)

# ============ Background Tasks ============

async def _execute_scraping_task(job_id: int):
    """
    Execute scraping job in background
    
    Args:
        job_id: Job ID to execute
    """
    # Create a new database session for this task
    from database import async_session
    
    async with async_session() as db_session:
        try:
            log_callback = await create_log_callback(job_id)
            manager = ScrapingJobManager(db_session, log_callback=log_callback)
            
            # Execute scraping
            await manager.execute_job(job_id)
            
        except Exception as e:
            logger.error(f"Error in scraping task {job_id}: {e}", exc_info=True)

# ============ Application Entry Point ============

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
