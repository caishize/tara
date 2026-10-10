"""
Pinduoduo (拼多多) Price Provider
Fetches product prices from Pinduoduo
"""
import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from .base import (
    BasePriceProvider,
    PriceData,
    ParseError,
    ProductNotFoundError,
)
from .platform_detector import Platform, extract_product_id
from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class PDDPriceProvider(BasePriceProvider):
    """
    Price provider for Pinduoduo (拼多多)

    Note: PDD heavily uses JavaScript rendering, success rate may be lower
    """

    platform = Platform.PDD

    # Mobile page URL template
    MOBILE_URL_TEMPLATE = "https://mobile.yangkeduo.com/goods.html?goods_id={product_id}"

    async def parse_price(self, html: str, url: str) -> PriceData:
        """Parse price from PDD page"""
        product_id = extract_product_id(url, Platform.PDD)
        if not product_id:
            raise ProductNotFoundError(f"Cannot extract product ID from URL: {url}")

        price = self._extract_price_from_html(html)
        if price is None:
            raise ParseError("Cannot find price in PDD page (JS rendering may be required)")

        product_name = self._extract_name_from_html(html) or f"拼多多商品 {product_id}"

        return PriceData(
            product_id=product_id,
            product_name=product_name,
            platform=self.platform.value,
            current_price=price,
            product_url=url,
            checked_at=utc_now(),
        )

    def _extract_price_from_html(self, html: str) -> Optional[float]:
        """Extract price from HTML"""
        # Try to find price in embedded JSON/JavaScript
        patterns = [
            r'"price"\s*:\s*(\d+)',  # Price in cents
            r'"minGroupPrice"\s*:\s*(\d+)',
            r'"minNormalPrice"\s*:\s*(\d+)',
            r'"marketPrice"\s*:\s*(\d+)',
            r'data-price="(\d+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    # PDD prices are often in cents (分)
                    price_cents = int(match.group(1))
                    if price_cents > 100:  # Likely in cents
                        price = price_cents / 100
                    else:
                        price = float(price_cents)
                    if price > 0:
                        return price
                except ValueError:
                    continue

        # Try decimal prices
        decimal_patterns = [
            r'"price"\s*:\s*"?([\d.]+)"?',
            r'class="price[^"]*"[^>]*>([\d.]+)',
        ]

        for pattern in decimal_patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    price = float(match.group(1))
                    if price > 0:
                        return price
                except ValueError:
                    continue

        # BeautifulSoup fallback
        soup = BeautifulSoup(html, "lxml")
        price_elements = soup.select("[class*=price], [class*=Price]")

        for element in price_elements:
            text = element.get_text(strip=True)
            match = re.search(r"[\d.]+", text)
            if match:
                try:
                    price = float(match.group())
                    if price > 0:
                        return price
                except ValueError:
                    continue

        return None

    def _extract_name_from_html(self, html: str) -> Optional[str]:
        """Extract product name from HTML"""
        patterns = [
            r'"goodsName"\s*:\s*"([^"]+)"',
            r'"goods_name"\s*:\s*"([^"]+)"',
            r'"title"\s*:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                name = match.group(1)
                if name and len(name) > 2:
                    return name[:200]

        soup = BeautifulSoup(html, "lxml")
        title_selectors = [
            ".goods-name",
            ".title",
            "title",
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if name:
                    name = re.sub(r"-拼多多.*$", "", name)
                    return name[:200]

        return None
