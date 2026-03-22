"""
MercadoLibre scraper implementation using Playwright + lxml
"""
import logging
from typing import List, Optional, Callable
from lxml import html
import httpx

from .base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

class MercadoLibreScraper(BaseScraper):
    """
    MercadoLibre scraper
    Scrapes products from MercadoLibre with anti-bot handling
    """
    
    BASE_URL = "https://listado.mercadolibre.com.co"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-CO,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    def __init__(self, log_callback: Optional[Callable] = None):
        super().__init__(log_callback)
        self.client = None
        self.products = []
    
    async def _init_client(self):
        """Initialize HTTP client with proper headers"""
        if not self.client:
            self.client = httpx.AsyncClient(headers=self.HEADERS, timeout=30.0)
    
    async def scrape(self, query: str) -> List[ScrapedProduct]:
        """
        Scrape MercadoLibre products
        
        Args:
            query: Search query string
            
        Returns:
            List of ScrapedProduct objects
        """
        try:
            await self.send_log(
                f"🔍 Iniciando scraping en MercadoLibre para: '{query}'",
                "info"
            )
            
            # Search URL
            if query.startswith("http"):
                search_url = query
            else:
                # MercadoLibre search URLs are path-based, not underscore hostnames
                search_url = f"{self.BASE_URL}/{query.replace(' ', '-')}"
            
            await self.send_log(
                f"📡 Conectando a {search_url}",
                "info"
            )

            # Prefer Playwright (renders JS)
            html_content = None
            try:
                await self.send_log("🧭 Usando navegador real (Playwright)...", "info")
                html_content = await self._fetch_with_playwright(search_url)
            except ImportError:
                await self.send_log(
                    "❌ Playwright no instalado. Instala con: pip install playwright "
                    "y luego: python -m playwright install chromium",
                    "error"
                )
                return []
            except Exception as e:
                await self.send_log(
                    f"⚠️ Playwright falló ({e}). Intentando HTTPX...",
                    "warning"
                )
                await self._init_client()
                html_content = await self._fetch_with_httpx(search_url)

            if not html_content:
                await self.send_log("❌ No se pudo obtener HTML", "error")
                return []

            if self._is_js_challenge(html_content):
                await self.send_log(
                    "⚠️ MercadoLibre devolvió un desafío anti-bot. "
                    "Si persiste, será necesario ajustar evasión o usar API.",
                    "warning"
                )

            await self.send_log("✓ Página cargada correctamente", "success")

            # Parse HTML
            products = await self._parse_products(html_content)
            
            await self.send_log(
                f"✓ Se encontraron {len(products)} productos",
                "success"
            )
            
            self.products = products
            return products
            
        except httpx.HTTPStatusError as e:
            error_msg = f"❌ Error HTTP {e.response.status_code}: {e.response.reason_phrase}"
            await self.send_log(error_msg, "error")
            self.logger.error(error_msg)
            return []
            
        except Exception as e:
            error_msg = f"❌ Error durante scraping: {str(e)}"
            await self.send_log(error_msg, "error")
            self.logger.error(error_msg, exc_info=True)
            return []

    async def _fetch_with_httpx(self, url: str) -> str:
        """Fetch HTML using HTTPX (no JS rendering)"""
        response = await self.client.get(url)
        response.raise_for_status()
        return response.text

    async def _fetch_with_playwright(self, url: str) -> str:
        """Fetch HTML using Playwright (JS rendering)"""
        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
        except Exception as e:
            raise ImportError("playwright not installed") from e

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                user_agent=self.HEADERS.get("User-Agent"),
                locale="es-CO",
                extra_http_headers={
                    k: v for k, v in self.HEADERS.items()
                    if k.lower() != "user-agent"
                },
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Wait for product list (best-effort)
                try:
                    await page.wait_for_selector(
                        "li.ui-search-layout__item, li.ui-search-layout, .ui-search-results",
                        timeout=20000
                    )
                except PlaywrightTimeoutError:
                    await self.send_log(
                        "⚠️ No se detectaron productos a tiempo; leyendo HTML igual.",
                        "warning"
                    )
                # MercadoLibre suele hidratar imagenes con lazy load; hacemos scroll corto
                # para forzar picture/source/srcset antes de capturar el HTML final.
                try:
                    await page.wait_for_timeout(1200)
                    for step in range(3):
                        await page.evaluate(
                            "(y) => window.scrollTo({ top: y, behavior: 'instant' })",
                            (step + 1) * 900
                        )
                        await page.wait_for_timeout(500)
                    await page.evaluate(
                        "() => window.scrollTo({ top: 0, behavior: 'instant' })"
                    )
                    await page.wait_for_timeout(300)
                except Exception:
                    pass
                html_content = await page.content()
            finally:
                await context.close()
                await browser.close()

        return html_content

    def _is_js_challenge(self, html_content: str) -> bool:
        """Detect common anti-bot JS challenges"""
        lowered = html_content.lower()
        indicators = [
            "this page requires javascript",
            "_bmstate",
            "captcha",
            "robot check",
            "challenge"
        ]
        return any(indicator in lowered for indicator in indicators)
    
    async def _parse_products(self, html_content: str) -> List[ScrapedProduct]:
        """
        Parse HTML and extract product information
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            List of ScrapedProduct objects
        """
        products = []
        try:
            tree = html.fromstring(html_content)
            
            # XPath selectors for MercadoLibre
            # Product items container
            item_locator = (
                "//li[contains(@class, 'ui-search-layout__item')]"
                " | //li[contains(@class, 'ui-search-layout')]"
                " | //div[contains(@class, 'ui-search-result__wrapper')]"
            )
            items = tree.xpath(item_locator)
            
            await self.send_log(
                f"📊 Procesando {len(items)} elementos...",
                "info"
            )
            products_with_image = 0
            first_item_without_image = None

            for index, item in enumerate(items, 1):
                try:
                    product = self._extract_product_data(item)
                    if product:
                        products.append(product)
                        if product.image_url:
                            products_with_image += 1
                        elif first_item_without_image is None:
                            first_item_without_image = item
                        await self.send_log(
                            f"✓ Producto {index}: {product.title[:50]}...",
                            "success"
                        )
                except Exception as e:
                    self.logger.warning(f"Error parsing product {index}: {e}")
                    continue
            
            if items and not products:
                await self._dump_first_item_for_debug(items[0])
                await self.send_log(
                    "⚠️ No se pudo extraer título/precio. Guardé el primer item "
                    "en /tmp/ml_item.html para ajustar selectores.",
                    "warning"
                )
            elif products:
                await self.send_log(
                    f"🖼️ Imagenes capturadas: {products_with_image} de {len(products)} productos",
                    "info"
                )
                if products_with_image == 0 and first_item_without_image is not None:
                    await self._dump_missing_image_debug(first_item_without_image)
                    await self.send_log(
                        "⚠️ Guardé una card sin imagen en /tmp/ml_no_image_item.html para ajustar selectores.",
                        "warning"
                    )

            return products
            
        except Exception as e:
            self.logger.error(f"Error parsing HTML: {e}")
            return products
    
    def _extract_product_data(self, item) -> Optional[ScrapedProduct]:
        """
        Extract product data from item element
        
        Args:
            item: lxml element
            
        Returns:
            ScrapedProduct or None
        """
        try:
            # Title (MercadoLibre changes classes often; use a few fallbacks)
            title_elem = item.xpath(
                ".//h2[contains(@class,'ui-search-item__title')]"
                " | .//h2[contains(@class,'poly-component__title')]"
                " | .//h2//span"
                " | .//span[contains(@class,'ui-search-item__title')]"
                " | .//a[contains(@class,'ui-search-link')]//h2"
                " | .//a[contains(@class,'poly-component__title')]"
                " | .//span[contains(@class,'poly-component__title')]"
            )
            title = title_elem[0].text_content().strip() if title_elem else ""

            # Fallback: use anchor text if title missing
            if not title:
                anchors = item.xpath(".//a[@href]")
                best = ""
                for a in anchors:
                    text = " ".join(a.text_content().split())
                    if len(text) > len(best):
                        best = text
                title = best.strip()
            
            if not title:
                return None
            
            # Price (current price) - avoid installments and strikethrough
            current_candidates = item.xpath(
                ".//span[("
                "contains(@class,'andes-money-amount__fraction')"
                " or contains(@class,'price-tag-fraction')"
                " or contains(@class,'ui-search-price__fraction')"
                ")]"
                "[not(ancestor::s)]"
                "[not(ancestor::*[contains(@class,'installments') or contains(@class,'poly-price__installments')])]"
            )

            candidate_prices = []
            for elem in current_candidates:
                text = elem.text_content().strip()
                val = self.normalize_price(text)
                if val:
                    candidate_prices.append(val)

            # Prefer the highest candidate to avoid installment/partial values
            price = max(candidate_prices) if candidate_prices else 0.0

            # Original price (if on sale)
            original_candidates = item.xpath(
                ".//s[contains(@class,'ui-search-price__regular-price')]"
                "//span[contains(@class,'andes-money-amount__fraction') or contains(@class,'price-tag-fraction') or contains(@class,'ui-search-price__fraction')]"
            )
            original_prices = []
            for elem in original_candidates:
                text = elem.text_content().strip()
                val = self.normalize_price(text)
                if val:
                    original_prices.append(val)

            original_price = max(original_prices) if original_prices else None
            if original_price and original_price <= price:
                original_price = None
            
            # Calculate discount
            discount_pct = None
            if original_price and original_price > price:
                discount_pct = self.calculate_discount(original_price, price)
            
            # Product URL
            link_elem = item.xpath(
                ".//a[contains(@class,'ui-search-link')]"
                " | .//a[contains(@class,'poly-component__title')]"
                " | .//a[contains(@href,'mercadolibre.com.co')]"
            )
            product_url = link_elem[0].get("href", "") if link_elem else ""
            
            # Image URL
            img_elem = item.xpath(
                ".//picture//source[@srcset]"
                " | .//picture//source[@data-srcset]"
                " | .//picture//source[@data-src]"
                " | .//source[@srcset]"
                " | .//source[@data-srcset]"
                " | .//source[@data-src]"
                " | .//img[contains(@class,'ui-search-result-image__element')]"
                " | .//img[contains(@class,'ui-search-result__image')]"
                " | .//img[contains(@class,'lazy-load')]"
                " | .//img[contains(@class,'poly-component__picture')]"
                " | .//img[contains(@class,'poly-card__portada')]"
                " | .//img[@data-src]"
                " | .//img[@data-srcset]"
                " | .//img[@srcset]"
                " | .//img[@src]"
                " | .//img[@data-original]"
                " | .//*[@data-src]"
                " | .//*[@data-srcset]"
                " | .//*[@style[contains(.,'background-image')]]"
            )
            image_url = ""
            for img in img_elem:
                image_url = self._extract_image_candidate(img)
                if image_url:
                    break

            # Rating and review count
            rating = None
            review_count = None
            rating_elem = item.xpath(".//span[@class='ui-search-reviews__rating-number']")
            if rating_elem:
                try:
                    rating = float(rating_elem[0].text_content().strip())
                except ValueError:
                    pass
            
            review_elem = item.xpath(".//span[@class='ui-search-reviews__amount']")
            if review_elem:
                try:
                    review_text = review_elem[0].text_content().strip()
                    # Extract number from text like "(123)"
                    review_count = int(''.join(filter(str.isdigit, review_text)))
                except ValueError:
                    pass
            
            return ScrapedProduct(
                title=title,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                currency="COP",  # Colombian Peso
                image_url=image_url,
                product_url=product_url,
                rating=rating,
                review_count=review_count,
                stock_status="In Stock"  # MercadoLibre usually shows available items
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting product data: {e}")
            return None

    async def _dump_first_item_for_debug(self, item) -> None:
        """Dump first item HTML to a temp file for debugging selectors."""
        try:
            from lxml import etree
            html_str = etree.tostring(item, encoding="unicode", pretty_print=True)
            with open("/tmp/ml_item.html", "w", encoding="utf-8") as f:
                f.write(html_str)
        except Exception as e:
            self.logger.warning(f"Could not dump debug item: {e}")

    async def _dump_missing_image_debug(self, item) -> None:
        """Dump a product card that did not yield an image URL."""
        try:
            from lxml import etree
            html_str = etree.tostring(item, encoding="unicode", pretty_print=True)
            with open("/tmp/ml_no_image_item.html", "w", encoding="utf-8") as f:
                f.write(html_str)
        except Exception as e:
            self.logger.warning(f"Could not dump missing-image item: {e}")
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()

    def _extract_image_candidate(self, node) -> str:
        """Extract the best usable image URL from img/source/style attributes."""
        import re

        candidates = [
            node.get("src", ""),
            node.get("data-src", ""),
            node.get("data-original", ""),
            node.get("data-srcset", ""),
            node.get("srcset", ""),
            node.get("data-recom-src", ""),
        ]

        style = node.get("style", "")
        if style:
            match = re.search(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", style)
            if match:
                candidates.append(match.group(2))

        for raw in candidates:
            candidate = self._normalize_image_url(raw)
            if candidate:
                return candidate
        return ""

    def _normalize_image_url(self, value: str) -> str:
        """Normalize src/srcset values and ignore placeholders."""
        if not value:
            return ""

        raw = value.strip()
        if not raw:
            return ""

        if "," in raw:
            parts = [p.strip().split(" ")[0] for p in raw.split(",") if p.strip()]
            raw = parts[-1] if parts else raw
        elif " " in raw and raw.startswith("http"):
            raw = raw.split(" ")[0]

        if raw.startswith("//"):
            raw = f"https:{raw}"

        lowered = raw.lower()
        if (
            lowered.startswith("data:image")
            or "transparent" in lowered
            or "pixel" in lowered
            or raw == "#"
        ):
            return ""

        return raw
