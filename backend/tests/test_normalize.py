"""
Unit tests for scraper price normalization
"""
import pytest
from scraper.base import BaseScraper, ScrapedProduct
from typing import List


class DummyScraper(BaseScraper):
    async def scrape(self, query: str) -> List[ScrapedProduct]:
        return []


@pytest.fixture
def scraper():
    return DummyScraper()


def test_normalize_simple_dollar(scraper):
    assert scraper.normalize_price("$100") == 100.0
    assert scraper.normalize_price("$100.50") == 100.50
    assert scraper.normalize_price("1,200.00") == 1200.00


def test_normalize_cop_and_latam_formats(scraper):
    # Colombian peso format: 3.500.000 or 3.500.000,00
    assert scraper.normalize_price("$ 3.500.000") == 3500000.0
    assert scraper.normalize_price("3.500.000,50") == 3500000.50


def test_normalize_empty_or_invalid(scraper):
    assert scraper.normalize_price("") == 0.0
    assert scraper.normalize_price("N/A") == 0.0
    assert scraper.normalize_price("Agotado") == 0.0


def test_calculate_discount(scraper):
    assert scraper.calculate_discount(100.0, 80.0) == 20.0
    assert scraper.calculate_discount(200.0, 150.0) == 25.0
    assert scraper.calculate_discount(0.0, 50.0) == 0.0
