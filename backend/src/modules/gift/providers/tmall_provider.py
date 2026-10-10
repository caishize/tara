"""
Tmall (天猫) Price Provider
Fetches product prices from Tmall.com
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


class TmallPriceProvider(BasePriceProvider):
    """
    Price provider for Tmall.com (天猫)

    Similar to Taobao but with different page structure
    """

    platform = Platform.TMALL

    async def parse_price(self, html: str, url: str) -> PriceData:
        """Parse price from Tmall page"""
        product_id = extract_product_id(url, Platform.TMALL)
        if not product_id:
            raise ProductNotFoundError(f"Cannot extract product ID from URL: {url}")

        price = self._extract_price_from_html(html)
        if price is None:
            raise ParseError("Cannot find price in Tmall page")

        product_name = self._extract_name_from_html(html) or f"天猫商品 {product_id}"

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
        # Try JSON patterns
        patterns = [
            r'"price"\s*:\s*"?([\d.]+)"?',
            r'"defaultItemPrice"\s*:\s*"?([\d.]+)"?',
            r'"priceInfo"[^}]*"price"\s*:\s*"?([\d.]+)"?',
            r'data-price="([\d.]+)"',
            r'tm-price[^>]*>([\d.]+)',
        ]

        for pattern in patterns:
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
        price_selectors = [
            ".tm-price",
            ".tm-promo-price",
            "[class*=price]",
        ]

        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
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
            r'"title"\s*:\s*"([^"]+)"',
            r'"itemTitle"\s*:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                name = match.group(1)
                if name and len(name) > 2:
                    return name[:200]

        soup = BeautifulSoup(html, "lxml")
        title_selectors = [
            "h1",
            ".tb-detail-hd",
            "title",
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if name:
                    name = re.sub(r"-.*天猫.*$", "", name)
                    return name[:200]

        return None
