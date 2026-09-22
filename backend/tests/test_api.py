"""
Tests for FastAPI endpoints
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "EcomScraper"


@pytest.mark.asyncio
async def test_openapi_available():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "/api/health" in data["paths"]
        assert "/api/jobs" in data["paths"]
        assert "/api/jobs/{job_id}/logs" in data["paths"]
        assert "/api/jobs/{job_id}/cancel" in data["paths"]


@pytest.mark.asyncio
async def test_create_job_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing query_url and query_string
        response = await client.post("/api/jobs", json={
            "source": "mercadolibre",
        })
        assert response.status_code == 400

        # Invalid filter_mode
        response = await client.post("/api/jobs", json={
            "source": "amazon",
            "query_string": "test",
            "filter_mode": "invalid_mode",
        })
        assert response.status_code == 400
