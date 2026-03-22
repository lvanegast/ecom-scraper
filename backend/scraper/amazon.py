"""
Amazon scraper implementation using Playwright + lxml
"""
import logging
import os
from typing import List, Optional, Callable
import httpx
from lxml import html

from .base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

class AmazonScraper(BaseScraper):
    """
    Amazon scraper
    Scrapes products from Amazon with anti-bot handling and IP block detection
    """
    
    BASE_URL = "https://www.amazon.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.amazon.com/",
    }
    
    def __init__(self, log_callback: Optional[Callable] = None, filter_mode: str = "smart"):
        super().__init__(log_callback)
        self.client = None
        self.products = []
        self.max_retries = 3
        self.filter_mode = filter_mode
        try:
            env_pages = int(os.getenv("AMAZON_MAX_PAGES", "1"))
        except ValueError:
            env_pages = 1
        self.max_pages = max(1, min(env_pages, 5))
        self.accessory_terms = {
            "case", "cover", "protector", "screen", "screen protector", "glass",
            "charger", "cable", "adapter", "dock", "stand", "wallet", "strap",
            "holder", "mount", "lens", "tempered", "proteccion", "funda",
            "carcasa", "protector de pantalla",
        }
        
    async def _init_client(self):
        """Initialize HTTP client with proper headers and cookies"""
        if not self.client:
            self.client = httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=30.0,
                follow_redirects=True
            )
    
    async def scrape(self, query: str) -> List[ScrapedProduct]:
        """
        Scrape Amazon products
        
        Args:
            query: Search query string or product URL
            
        Returns:
            List of ScrapedProduct objects
        """
        try:
            await self.send_log(
                f"🔍 Iniciando scraping en Amazon para: '{query}'",
                "info"
            )
            
            # Build search URL(s)
            if query.startswith("http"):
                search_urls = [query]
            else:
                q = query.replace(" ", "+")
                search_url = f"{self.BASE_URL}/s?k={q}&i=electronics"
                # If searching for iPhone, bias to Apple brand results
                if "iphone" in query.lower():
                    search_url += "&rh=p_89:Apple"
                # Order by lowest price first (first page only)
                if "s=" not in search_url:
                    search_url += "&s=price-asc-rank"
                if self.max_pages == 1:
                    await self.send_log(
                        "↕️ Ordenando por precio (menor a mayor) y usando solo la primera página.",
                        "info"
                    )
                else:
                    await self.send_log(
                        f"↕️ Ordenando por precio (menor a mayor) y usando {self.max_pages} páginas.",
                        "info"
                    )
                search_urls = [search_url]
                if self.max_pages > 1:
                    search_urls += [f"{search_url}&page={p}" for p in range(2, self.max_pages + 1)]
            
            await self.send_log(
                f"📡 Conectando a Amazon...",
                "info"
            )

            # Prefer Playwright (renders JS)
            products = []
            seen_urls = set()
            for idx, url in enumerate(search_urls, 1):
                await self.send_log(
                    f"📄 Página {idx}/{len(search_urls)}: cargando resultados...",
                    "info"
                )
                html_content = None
                try:
                    await self.send_log("🧭 Usando navegador real (Playwright)...", "info")
                    html_content = await self._fetch_with_playwright(url)
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
                    html_content = await self._fetch_with_httpx(url)

                if not html_content:
                    await self.send_log("❌ No se pudo obtener HTML", "error")
                    continue

                # Check if IP is blocked
                if self._is_ip_blocked(html_content):
                    error_msg = "⚠️ Amazon bloqueó la sesión (captcha/robot). " \
                               "Podrías necesitar proxies o rotación."
                    await self.send_log(error_msg, "warning")
                    self.logger.warning(error_msg)
                    break

                await self.send_log("✓ Página cargada correctamente", "success")

                # Parse HTML
                page_products = await self._parse_products(html_content)
                for p in page_products:
                    if p.product_url and p.product_url in seen_urls:
                        continue
                    if p.product_url:
                        seen_urls.add(p.product_url)
                    products.append(p)

            # Filter accessories if query is a keyword search
            if query and not query.startswith("http") and self.filter_mode != "off":
                before = len(products)
                filtered = self._filter_by_query(query, products)
                if len(filtered) != before:
                    await self.send_log(
                        f"🔎 Filtrados por query: {len(filtered)} de {before} productos",
                        "info"
                    )
                # If filter removed everything, keep original list in smart mode
                if self.filter_mode == "smart" and not filtered and products:
                    await self.send_log(
                        "⚠️ Filtro dejó 0 resultados; devolviendo lista sin filtrar.",
                        "warning"
                    )
                products = filtered or (products if self.filter_mode == "smart" else [])
            
            await self.send_log(
                f"✓ Se encontraron {len(products)} productos",
                "success"
            )
            
            self.products = products
            return products
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                error_msg = "❌ Amazon devolvió error 503 (servicio no disponible). " \
                           "Puede deberse a protección anti-bot."
            elif e.response.status_code == 403:
                error_msg = "❌ Acceso denegado (403). IP podría estar bloqueada."
            else:
                error_msg = f"❌ Error HTTP {e.response.status_code}"
            
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
                locale="en-US",
                extra_http_headers={
                    k: v for k, v in self.HEADERS.items()
                    if k.lower() != "user-agent"
                },
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Wait for search results (best-effort)
                try:
                    await page.wait_for_selector(
                        "div[data-component-type='s-search-result'], .s-main-slot",
                        timeout=20000
                    )
                except PlaywrightTimeoutError:
                    await self.send_log(
                        "⚠️ No se detectaron resultados a tiempo; leyendo HTML igual.",
                        "warning"
                    )
                html_content = await page.content()
            finally:
                await context.close()
                await browser.close()

        return html_content
    
    def _is_ip_blocked(self, html_content: str) -> bool:
        """
        Check if IP is blocked by Amazon
        
        Args:
            html_content: Response HTML
            
        Returns:
            True if IP appears to be blocked
        """
        blocked_indicators = [
            "captcha",
            "503 Service Unavailable",
            "To discuss automated access to Amazon data",
            "Robot Check"
        ]
        
        html_lower = html_content.lower()
        return any(indicator.lower() in html_lower for indicator in blocked_indicators)
    
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
            
            # Amazon product selectors
            items = tree.xpath("//div[@data-component-type='s-search-result' and @data-asin!='']")
            
            if not items:
                # Fallback
                items = tree.xpath("//div[contains(@class, 's-result-item')]")
            
            await self.send_log(
                f"📊 Procesando {len(items)} elementos...",
                "info"
            )
            
            for index, item in enumerate(items[:60], 1):  # Limit to 60 products
                try:
                    product = self._extract_product_data(item)
                    if product:
                        products.append(product)
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
                    "⚠️ No se pudo extraer títulos/precios. Guardé el primer item "
                    "en /tmp/amz_item.html para ajustar selectores.",
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
            # Title (prefer h2 title, avoid badges)
            title = ""
            title_candidates = item.xpath(
                ".//h2//span[not(contains(@class,'a-badge'))]"
            )
            if title_candidates:
                title = " ".join([t.strip() for t in title_candidates[0].itertext()]).strip()
            if not title:
                title_elem = item.xpath(".//h2//a//span")
                title = title_elem[0].text_content().strip() if title_elem else ""
            if not title:
                h2_elem = item.xpath(".//h2")
                title = h2_elem[0].text_content().strip() if h2_elem else ""

            if not title or len(title) < 3 or "amazon's choice" in title.lower():
                return None
            
            # Price (try several selectors)
            price_text = ""
            offscreen = item.xpath(".//span[@class='a-price']//span[@class='a-offscreen']")
            if offscreen:
                price_text = offscreen[0].text_content().strip()
            if not price_text:
                whole_elem = item.xpath(".//span[@class='a-price-whole']")
                frac_elem = item.xpath(".//span[@class='a-price-fraction']")
                if whole_elem:
                    whole = whole_elem[0].text_content().strip()
                    frac = frac_elem[0].text_content().strip() if frac_elem else ""
                    price_text = f"{whole}.{frac}" if frac else whole
            if not price_text:
                alt_price = item.xpath(".//span[contains(@class,'a-color-price')]")
                if alt_price:
                    price_text = alt_price[0].text_content().strip()
            if not price_text:
                price_text = "0"
            price = self.normalize_price(price_text)
            currency = self._detect_currency(price_text, item)
            
            # Product URL
            link_elem = item.xpath(".//h2//a[@href]")
            product_url = link_elem[0].get("href", "") if link_elem else ""
            if product_url and not product_url.startswith("http"):
                product_url = f"{self.BASE_URL}{product_url}"
            if not product_url:
                asin = item.xpath("./@data-asin")
                if asin and asin[0]:
                    product_url = f"{self.BASE_URL}/dp/{asin[0]}"
            
            # Image URL
            img_elem = item.xpath(".//img[@class='s-image']")
            image_url = img_elem[0].get("src", "") if img_elem else ""
            
            # Rating
            rating = None
            rating_elem = item.xpath(".//span[@aria-label and contains(@aria-label, 'out of 5 stars')]")
            if rating_elem:
                try:
                    rating_text = rating_elem[0].get("aria-label", "")
                    rating = float(rating_text.split()[0])
                except (ValueError, IndexError):
                    pass
            
            # Review count
            review_elem = item.xpath(".//span[contains(text(), 'K') or contains(text(), ',')]")
            review_count = None
            
            return ScrapedProduct(
                title=title,
                price=price,
                currency=currency,
                image_url=image_url,
                product_url=product_url,
                rating=rating,
                review_count=review_count,
                stock_status="In Stock"
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting product data: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()

    async def _dump_first_item_for_debug(self, item) -> None:
        """Dump first item HTML to a temp file for debugging selectors."""
        try:
            from lxml import etree
            html_str = etree.tostring(item, encoding="unicode", pretty_print=True)
            with open("/tmp/amz_item.html", "w", encoding="utf-8") as f:
                f.write(html_str)
        except Exception as e:
            self.logger.warning(f"Could not dump debug item: {e}")

    def _filter_by_query(self, query: str, products: List[ScrapedProduct]) -> List[ScrapedProduct]:
        """Filter out accessories and weak matches for keyword queries."""
        q = self._normalize(query)
        q_tokens = [t for t in q.split() if t]
        allow_accessory = any(term in q for term in self.accessory_terms)

        filtered: List[ScrapedProduct] = []
        for p in products:
            title = self._normalize(p.title or "")
            if not title:
                continue
            # Basic token match
            matches = sum(1 for t in q_tokens if t in title)
            if matches < 1:
                continue
            # Drop accessory-only items unless user asked for them
            if not allow_accessory and any(term in title for term in self.accessory_terms):
                continue
            filtered.append(p)
        return filtered

    def _normalize(self, text: str) -> str:
        import re
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _detect_currency(self, price_text: str, item) -> str:
        """Best-effort currency detection from visible Amazon price text."""
        haystack_parts = [price_text or ""]

        aria_candidates = item.xpath(".//*[@aria-label]/@aria-label")
        if aria_candidates:
            haystack_parts.extend(aria_candidates[:8])

        text_candidates = item.xpath(".//span/text()")
        if text_candidates:
            haystack_parts.extend([t.strip() for t in text_candidates[:20] if t.strip()])

        haystack = " ".join(haystack_parts).upper()

        if "COP" in haystack or "COL$" in haystack:
            return "COP"
        if "MXN" in haystack or "MX$" in haystack:
            return "MXN"
        if "EUR" in haystack or "€" in haystack:
            return "EUR"
        if "GBP" in haystack or "£" in haystack:
            return "GBP"
        if "USD" in haystack or "US$" in haystack:
            return "USD"

        return "USD"
