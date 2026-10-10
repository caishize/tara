"""
JD (京东) Price Provider
Fetches product prices from JD.com
"""
import re
import json
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from .base import (
    BasePriceProvider,
    PriceData,
    ParseError,
    ProductNotFoundError,
    NetworkError,
)
from .platform_detector import Platform, extract_product_id
from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class JDPriceProvider(BasePriceProvider):
    """
    Price provider for JD.com (京东)

    Uses two strategies:
    1. JD Price API (p.3.cn) - Fast and reliable for price
    2. HTML parsing - Fallback for product name and details
    """

    platform = Platform.JD
    timeout: float = 30.0  # Longer timeout for JD

    # JD Price API endpoint
    PRICE_API_URL = "https://p.3.cn/prices/mgets"

    async def get_price(self, product_url: str) -> PriceData:
        """
        Get price from JD

        Tries price API first, falls back to HTML parsing
        """
        platform_name = self.platform.value

        # Check if platform is blocked
        if self.anti_crawler.is_platform_blocked(platform_name):
            remaining = self.anti_crawler.get_block_remaining_seconds(platform_name)
            from .base import PlatformBlockedError
            raise PlatformBlockedError(
                f"Platform {platform_name} is blocked for {remaining:.0f} more seconds"
            )

        # Extract product ID
        product_id = extract_product_id(product_url, Platform.JD)
        if not product_id:
            raise ProductNotFoundError(f"Cannot extract product ID from URL: {product_url}")

        # Wait before request
        await self.anti_crawler.wait_before_request(platform_name)

        try:
            # Try API first
            price, original_price = await self._fetch_price_from_api(product_id)

            # Get product name from page (optional, don't fail if this fails)
            product_name = await self._fetch_product_name(product_url, product_id)

            self.anti_crawler.record_success(platform_name)

            return PriceData(
                product_id=product_id,
                product_name=product_name,
                platform=platform_name,
                current_price=price,
                original_price=original_price,
                product_url=product_url,
                checked_at=utc_now(),
                discount_percentage=self._calculate_discount(price, original_price),
            )

        except Exception as e:
            self.anti_crawler.record_failure(platform_name)
            raise

    async def _fetch_price_from_api(self, product_id: str) -> Tuple[float, Optional[float]]:
        """
        Fetch price from JD price API

        Args:
            product_id: JD product SKU ID

        Returns:
            Tuple of (current_price, original_price)
        """
        headers = self.anti_crawler.get_request_headers()
        headers["Referer"] = f"https://item.jd.com/{product_id}.html"

        params = {
            "skuIds": f"J_{product_id}",
            "type": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.PRICE_API_URL,
                    params=params,
                    headers=headers
                )

                if response.status_code != 200:
                    raise NetworkError(f"Price API returned {response.status_code}")

                # Parse JSON response
                # Response format: [{"id":"J_100026691566","p":"5999.00","m":"5999.00","op":"5999.00"}]
                data = response.json()

                if not data or len(data) == 0:
                    raise ProductNotFoundError(f"No price data for product {product_id}")

                price_info = data[0]
                current_price = float(price_info.get("p", 0))
                original_price = float(price_info.get("op", price_info.get("m", 0)))

                if current_price <= 0:
                    raise ParseError(f"Invalid price: {current_price}")

                return current_price, original_price if original_price > 0 else None

        except json.JSONDecodeError as e:
            raise ParseError(f"Failed to parse price API response: {e}")
        except httpx.TimeoutException:
            raise NetworkError("Price API request timeout")
        except httpx.HTTPError as e:
            raise NetworkError(f"Price API request failed: {e}")

    async def _fetch_product_name(
        self,
        product_url: str,
        product_id: str
    ) -> str:
        """
        Fetch product name from product page

        Args:
            product_url: Product page URL
            product_id: Product ID (fallback name)

        Returns:
            Product name
        """
        try:
            headers = self.anti_crawler.get_request_headers()

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(product_url, headers=headers)

                if response.status_code != 200:
                    return f"京东商品 {product_id}"

                html = response.text
                soup = BeautifulSoup(html, "lxml")

                # Try different selectors for product name
                name_selectors = [
                    "div.sku-name",
                    "div.itemInfo-wrap div.sku-name",
                    "h1.sku-name",
                    "title",
                ]

                for selector in name_selectors:
                    element = soup.select_one(selector)
                    if element:
                        name = element.get_text(strip=True)
                        # Clean up title tag content
                        if selector == "title":
                            name = name.replace("【图片 价格 品牌 报价】-京东", "").strip()
                            name = name.replace("-京东", "").strip()
                        if name:
                            return name[:200]  # Limit length

                return f"京东商品 {product_id}"

        except Exception as e:
            logger.warning(f"Failed to fetch product name: {e}")
            return f"京东商品 {product_id}"

    async def parse_price(self, html: str, url: str) -> PriceData:
        """
        Parse price from HTML (fallback method)

        Args:
            html: HTML content
            url: Product URL

        Returns:
            PriceData object
        """
        product_id = extract_product_id(url, Platform.JD)
        if not product_id:
            raise ProductNotFoundError(f"Cannot extract product ID from URL: {url}")

        soup = BeautifulSoup(html, "lxml")

        # Try to find price in HTML
        price = self._extract_price_from_html(soup)
        if price is None:
            raise ParseError("Cannot find price in page HTML")

        # Get product name
        product_name = self._extract_name_from_html(soup) or f"京东商品 {product_id}"

        return PriceData(
            product_id=product_id,
            product_name=product_name,
            platform=self.platform.value,
            current_price=price,
            product_url=url,
            checked_at=utc_now(),
        )

    def _extract_price_from_html(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract price from HTML"""
        price_selectors = [
            "span.p-price span",
            "span.price",
            "span.J-p-",
            "div.summary-price-wrap span.price",
        ]

        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                # Extract number from text
                match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                if match:
                    try:
                        price = float(match.group())
                        if price > 0:
                            return price
                    except ValueError:
                        continue

        return None

    def _extract_name_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product name from HTML"""
        name_selectors = [
            "div.sku-name",
            "h1.sku-name",
            "div.itemInfo-wrap div.sku-name",
        ]

        for selector in name_selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if name:
                    return name[:200]

        return None

    def _calculate_discount(
        self,
        current_price: float,
        original_price: Optional[float]
    ) -> Optional[float]:
        """Calculate discount percentage"""
        if original_price and original_price > current_price:
            discount = ((original_price - current_price) / original_price) * 100
            return round(discount, 1)
        return None
