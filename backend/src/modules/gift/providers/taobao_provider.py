"""
Taobao (淘宝) Price Provider
Fetches product prices from Taobao.com
"""
import re
import json
import logging
from typing import Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from .base import (
    BasePriceProvider,
    PriceData,
    ParseError,
    ProductNotFoundError,
    NetworkError,
    RateLimitedError,
)
from .platform_detector import Platform, extract_product_id
from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class TaobaoPriceProvider(BasePriceProvider):
    """
    Price provider for Taobao.com (淘宝)

    Uses H5 mobile page for better access (less anti-crawler)
    """

    platform = Platform.TAOBAO

    # H5 page URL template
    H5_URL_TEMPLATE = "https://h5.m.taobao.com/awp/core/detail.htm?id={product_id}"

    async def get_price(self, product_url: str) -> PriceData:
        """Get price from Taobao"""
        platform_name = self.platform.value

        if self.anti_crawler.is_platform_blocked(platform_name):
            remaining = self.anti_crawler.get_block_remaining_seconds(platform_name)
            from .base import PlatformBlockedError
            raise PlatformBlockedError(
                f"Platform {platform_name} is blocked for {remaining:.0f} more seconds"
            )

        product_id = extract_product_id(product_url, Platform.TAOBAO)
        if not product_id:
            raise ProductNotFoundError(f"Cannot extract product ID from URL: {product_url}")

        await self.anti_crawler.wait_before_request(platform_name)

        try:
            # Use H5 page URL
            h5_url = self.H5_URL_TEMPLATE.format(product_id=product_id)
            html = await self._fetch_page(h5_url)
            price_data = await self.parse_price(html, product_url)

            self.anti_crawler.record_success(platform_name)
            return price_data

        except Exception as e:
            self.anti_crawler.record_failure(platform_name)
            raise

    async def parse_price(self, html: str, url: str) -> PriceData:
        """Parse price from Taobao H5 page"""
        product_id = extract_product_id(url, Platform.TAOBAO)
        if not product_id:
            raise ProductNotFoundError(f"Cannot extract product ID from URL: {url}")

        # Try to find price in page data
        price = self._extract_price_from_html(html)
        if price is None:
            raise ParseError("Cannot find price in Taobao page")

        product_name = self._extract_name_from_html(html) or f"淘宝商品 {product_id}"

        return PriceData(
            product_id=product_id,
            product_name=product_name,
            platform=self.platform.value,
            current_price=price,
            product_url=url,
            checked_at=utc_now(),
        )

    def _extract_price_from_html(self, html: str) -> Optional[float]:
        """Extract price from HTML/JSON in page"""
        # Try to find price in JSON data embedded in page
        patterns = [
            r'"price"\s*:\s*"?([\d.]+)"?',
            r'"priceText"\s*:\s*"¥?([\d.]+)"?',
            r'"promotionPrice"\s*:\s*"?([\d.]+)"?',
            r'data-price="([\d.]+)"',
            r'class="price"[^>]*>¥?([\d.]+)',
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

        # Try BeautifulSoup parsing
        soup = BeautifulSoup(html, "lxml")
        price_elements = soup.select(".price, .tm-price, [class*=price]")

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
        # Try JSON data first
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

        # Try HTML parsing
        soup = BeautifulSoup(html, "lxml")
        title_selectors = [
            "h1.title",
            ".item-title",
            "title",
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if name:
                    # Clean up title
                    name = re.sub(r"-淘宝网$", "", name)
                    return name[:200]

        return None
