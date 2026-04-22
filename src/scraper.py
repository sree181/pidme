"""
Motion.com Ball Bearings Scraper
Uses Playwright for JS-rendered pages.

NOTE: motion.com implements aggressive WAF/bot protection.
In a production environment, run this from a residential IP with:
  - Proper browser fingerprinting via playwright-stealth
  - Per-domain rate limiting (3-5s delay)
  - User-agent rotation

For the MVP, we use pre-seeded data + this scraper as the live path
when network access allows it.
"""

import asyncio
import re
import json
from typing import Optional
from dataclasses import dataclass, field
from urllib.parse import urljoin, quote
import logging

logger = logging.getLogger(__name__)

CATEGORY_URL = "https://www.motion.com/products/Bearings/Ball%20Bearings"

# CSS selectors discovered via page inspection
SELECTORS = {
    "product_grid_item": '[class*="ProductCard"], [class*="product-card"], [data-testid*="product"]',
    "product_link": 'a[href*="/products/sku/"]',
    "product_name": 'h1, [class*="ProductName"], [class*="product-name"]',
    "spec_label": '[class*="spec-label"], [class*="attribute-label"], dt',
    "spec_value": '[class*="spec-value"], [class*="attribute-value"], dd',
    "product_image": 'img[class*="product"], img[alt*="bearing"], [class*="ProductImage"] img',
    "pagination_next": '[aria-label="Next page"], [class*="pagination"] a[rel="next"]',
}

# Known spec field name mappings from motion.com labels → our model fields
SPEC_MAP = {
    "bore diameter": "bore_diameter",
    "outside diameter": "outside_diameter",
    "overall width": "overall_width",
    "closure type": "closure_type",
    "bearing material": "bearing_material",
    "series": "series",
    "max rpm": "max_rpm",
    "weight": "weight",
    "radial dynamic load capacity": "radial_dynamic_load",
    "radial static load capacity": "radial_static_load",
    "internal clearance": "internal_clearance",
    "precision rating": "precision_rating",
    "product type": "product_type",
    "upc_no": "upc",
    "manufacturer catalog number": "mfr_part_number",
}


@dataclass
class ScrapedProduct:
    motion_sku: str = ""
    mfr_name: str = ""
    mfr_part_number: str = ""
    description: str = ""
    product_type: str = ""
    bore_diameter: str = ""
    outside_diameter: str = ""
    overall_width: str = ""
    closure_type: str = ""
    bearing_material: str = ""
    series: str = ""
    max_rpm: str = ""
    weight: str = ""
    radial_dynamic_load: str = ""
    radial_static_load: str = ""
    internal_clearance: str = ""
    precision_rating: str = ""
    upc: str = ""
    source_url: str = ""


async def scrape_category_page(page, url: str) -> list[str]:
    """
    Navigate to a category listing page and extract all product detail URLs.
    Returns list of product SKU URLs like /products/sku/XXXXXXXX
    """
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)  # JS hydration

    product_links = set()

    # Try to find product links by href pattern
    links = await page.query_selector_all('a[href*="/products/sku/"]')
    for link in links:
        href = await link.get_attribute("href")
        if href:
            full_url = urljoin("https://www.motion.com", href)
            product_links.add(full_url)

    # Handle "Load More" or pagination
    load_more = await page.query_selector('[class*="load-more"], button:has-text("Load More")')
    if load_more:
        for _ in range(3):  # Load up to 3 extra pages
            await load_more.click()
            await page.wait_for_timeout(2000)
            new_links = await page.query_selector_all('a[href*="/products/sku/"]')
            for link in new_links:
                href = await link.get_attribute("href")
                if href:
                    product_links.add(urljoin("https://www.motion.com", href))
            load_more = await page.query_selector('[class*="load-more"], button:has-text("Load More")')
            if not load_more:
                break

    logger.info(f"Found {len(product_links)} product URLs on category page")
    return list(product_links)


async def scrape_product_page(page, url: str) -> Optional[ScrapedProduct]:
    """
    Scrape a single product detail page and extract all spec data.
    """
    try:
        await page.goto(url, wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1500)
    except Exception as e:
        logger.warning(f"Failed to load {url}: {e}")
        return None

    product = ScrapedProduct(source_url=url)

    # Extract SKU from URL: /products/sku/02138118 -> 02138118
    sku_match = re.search(r"/products/sku/(\d+)", url)
    if sku_match:
        product.motion_sku = sku_match.group(1)

    # Get page title / product name (usually "MFR PART_NUMBER - description")
    try:
        h1 = await page.query_selector("h1")
        if h1:
            product.description = (await h1.inner_text()).strip()
    except Exception:
        pass

    # Try to find manufacturer name in breadcrumbs or product header
    try:
        mfr_elements = await page.query_selector_all(
            '[class*="brand"], [class*="manufacturer"], [class*="mfr"]'
        )
        for el in mfr_elements[:2]:
            text = (await el.inner_text()).strip()
            if text and len(text) < 60:
                product.mfr_name = text
                break
    except Exception:
        pass

    # Parse spec table: look for dt/dd or label/value pairs
    try:
        page_text = await page.inner_text("body")

        # Walk through known spec patterns
        for label_text, field_name in SPEC_MAP.items():
            # Case-insensitive search for spec in page text
            pattern = re.compile(
                rf"{re.escape(label_text)}\s*[:\·•]\s*([^\n·•]+)",
                re.IGNORECASE
            )
            match = pattern.search(page_text)
            if match:
                value = match.group(1).strip()
                setattr(product, field_name, value)

    except Exception as e:
        logger.warning(f"Spec extraction failed for {url}: {e}")

    # If we found mfr_part_number in description, try to extract mfr_name from title
    if not product.mfr_name and product.description:
        # Pattern: "SKF 6203" or "General Bearing Corporation 8702-88"
        title_match = re.match(r"^([A-Za-z][A-Za-z\s&\.]+?)\s+(\S+)", product.description)
        if title_match:
            product.mfr_name = title_match.group(1).strip()

    logger.info(f"Scraped: {product.motion_sku} | {product.mfr_name} {product.mfr_part_number}")
    return product


async def run_scraper(max_products: int = 50) -> list[ScrapedProduct]:
    """
    Main entry point: scrape motion.com ball bearings category.
    Returns list of ScrapedProduct objects.

    Usage:
        from scraper import run_scraper
        products = asyncio.run(run_scraper(max_products=100))
    """
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = await context.new_page()

        # Step 1: Get product URLs from category page
        try:
            product_urls = await scrape_category_page(page, CATEGORY_URL)
        except Exception as e:
            logger.error(f"Category scrape failed: {e}")
            await browser.close()
            return results

        # Step 2: Scrape each product page with delay
        for i, url in enumerate(product_urls[:max_products]):
            logger.info(f"[{i+1}/{min(len(product_urls), max_products)}] Scraping {url}")
            product = await scrape_product_page(page, url)
            if product:
                results.append(product)
            # Respectful rate limiting: 2-4 seconds between requests
            await asyncio.sleep(2.5)

        await browser.close()

    logger.info(f"Scrape complete: {len(results)} products collected")
    return results


# ── CLI runner ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    max_p = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    products = asyncio.run(run_scraper(max_p))
    print(json.dumps([p.__dict__ for p in products], indent=2))
