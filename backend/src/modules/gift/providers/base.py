"""
Base Price Provider (T034: Structured Logging)
Abstract base class for price service providers with built-in anti-crawler support
"""
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
import json

import httpx

from .platform_detector import Platform, detect_platform, extract_product_id
from .anti_crawler import AntiCrawlerManager, AntiCrawlerConfig, get_anti_crawler_manager
from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class StructuredPriceLogger:
    """
    Structured logger for price service requests (T034)

    Logs each request in JSON format with:
    - platform: The e-commerce platform
    - product_id: Product identifier
    - response_time_ms: Request duration in milliseconds
    - success: Whether request succeeded
    - correlation_id: Unique ID for request tracing
    - error_type: Type of error if failed
    """

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger

    def log_request(
        self,
        platform: str,
        product_id: str,
        product_url: str,
        success: bool,
        response_time_ms: int,
        price: Optional[float] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """Log a price fetch request in structured format"""
        log_data = {
            "event": "price_fetch",
            "correlation_id": correlation_id or str(uuid.uuid4())[:8],
            "platform": platform,
            "product_id": product_id,
            "product_url": product_url,
            "success": success,
            "response_time_ms": response_time_ms,
            "timestamp": utc_now().isoformat()
        }

        if success:
            log_data["price"] = price
            self.logger.info(
                f"Price fetch success: {platform}/{product_id} = ¥{price} ({response_time_ms}ms)",
                extra={"structured_data": json.dumps(log_data, ensure_ascii=False)}
            )
        else:
            log_data["error_type"] = error_type
            log_data["error_message"] = error_message
            self.logger.warning(
                f"Price fetch failed: {platform}/{product_id} - {error_type}: {error_message} ({response_time_ms}ms)",
                extra={"structured_data": json.dumps(log_data, ensure_ascii=False)}
            )

    def log_batch_summary(
        self,
        total_requests: int,
        successful: int,
        failed: int,
        total_time_ms: int,
        alerts_generated: int,
        correlation_id: Optional[str] = None
    ):
        """Log batch price check summary"""
        log_data = {
            "event": "batch_price_check",
            "correlation_id": correlation_id or str(uuid.uuid4())[:8],
            "total_requests": total_requests,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_requests if total_requests > 0 else 0,
            "total_time_ms": total_time_ms,
            "avg_time_ms": total_time_ms // total_requests if total_requests > 0 else 0,
            "alerts_generated": alerts_generated,
            "timestamp": utc_now().isoformat()
        }

        self.logger.info(
            f"Batch check complete: {successful}/{total_requests} success, {alerts_generated} alerts, {total_time_ms}ms total",
            extra={"structured_data": json.dumps(log_data, ensure_ascii=False)}
        )


# Global structured logger instance
structured_logger = StructuredPriceLogger()


class PriceProviderError(Exception):
    """Base exception for price provider errors"""
    pass


class NetworkError(PriceProviderError):
    """Network-related errors (connection, timeout)"""
    pass


class RateLimitedError(PriceProviderError):
    """Request was rate limited (403, captcha)"""
    pass


class ParseError(PriceProviderError):
    """Failed to parse price from page"""
    pass


class ProductNotFoundError(PriceProviderError):
    """Product page not found or product removed"""
    pass


class PlatformNotSupportedError(PriceProviderError):
    """Platform is not supported"""
    pass


class PlatformBlockedError(PriceProviderError):
    """Platform is temporarily blocked due to rate limiting"""
    pass


@dataclass
class PriceData:
    """Price data returned from provider"""
    product_id: str
    product_name: str
    platform: str
    current_price: float
    product_url: str
    checked_at: datetime
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    stock_status: bool = True
    merchant: Optional[str] = None
    price_type: str = "normal"  # normal, promotion, flash_sale

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "platform": self.platform,
            "current_price": self.current_price,
            "original_price": self.original_price,
            "discount_percentage": self.discount_percentage,
            "stock_status": self.stock_status,
            "merchant": self.merchant,
            "product_url": self.product_url,
            "checked_at": self.checked_at.isoformat(),
            "price_type": self.price_type,
        }


class BasePriceProvider(ABC):
    """
    Abstract base class for price providers

    Provides common functionality:
    - HTTP client with anti-crawler headers
    - Request throttling and rate limiting
    - Error handling and logging
    """

    platform: Platform = Platform.UNKNOWN
    timeout: float = 10.0

    def __init__(
        self,
        anti_crawler: Optional[AntiCrawlerManager] = None,
        timeout: Optional[float] = None
    ):
        """
        Initialize price provider

        Args:
            anti_crawler: Anti-crawler manager (uses default if None)
            timeout: Request timeout in seconds
        """
        self.anti_crawler = anti_crawler or get_anti_crawler_manager()
        if timeout:
            self.timeout = timeout

    @abstractmethod
    async def parse_price(self, html: str, url: str) -> PriceData:
        """
        Parse price information from HTML

        Args:
            html: HTML content of product page
            url: Original product URL

        Returns:
            PriceData object

        Raises:
            ParseError: If price cannot be extracted
        """
        pass

    async def get_price(self, product_url: str) -> PriceData:
        """
        Get current price for a product (T034: Structured Logging)

        Args:
            product_url: Product page URL

        Returns:
            PriceData object

        Raises:
            NetworkError: Connection or timeout error
            RateLimitedError: Request was rate limited
            ParseError: Failed to parse price
            ProductNotFoundError: Product not found
            PlatformBlockedError: Platform temporarily blocked
        """
        platform_name = self.platform.value
        correlation_id = str(uuid.uuid4())[:8]

        # Extract product ID for logging
        product_id = extract_product_id(product_url, self.platform) or "unknown"

        # Check if platform is blocked
        if self.anti_crawler.is_platform_blocked(platform_name):
            remaining = self.anti_crawler.get_block_remaining_seconds(platform_name)
            structured_logger.log_request(
                platform=platform_name,
                product_id=product_id,
                product_url=product_url,
                success=False,
                response_time_ms=0,
                error_type="PlatformBlockedError",
                error_message=f"Platform blocked for {remaining:.0f}s",
                correlation_id=correlation_id
            )
            raise PlatformBlockedError(
                f"Platform {platform_name} is blocked for {remaining:.0f} more seconds"
            )

        # Wait before request (anti-crawler)
        await self.anti_crawler.wait_before_request(platform_name)

        start_time = time.time()

        try:
            html = await self._fetch_page(product_url)
            price_data = await self.parse_price(html, product_url)

            # Record success
            self.anti_crawler.record_success(platform_name)

            elapsed_ms = int((time.time() - start_time) * 1000)

            # T034: Structured logging
            structured_logger.log_request(
                platform=platform_name,
                product_id=price_data.product_id,
                product_url=product_url,
                success=True,
                response_time_ms=elapsed_ms,
                price=price_data.current_price,
                correlation_id=correlation_id
            )

            return price_data

        except RateLimitedError as e:
            self.anti_crawler.record_failure(platform_name, is_rate_limited=True)
            elapsed_ms = int((time.time() - start_time) * 1000)
            structured_logger.log_request(
                platform=platform_name,
                product_id=product_id,
                product_url=product_url,
                success=False,
                response_time_ms=elapsed_ms,
                error_type="RateLimitedError",
                error_message=str(e),
                correlation_id=correlation_id
            )
            raise
        except (NetworkError, ParseError, ProductNotFoundError) as e:
            self.anti_crawler.record_failure(platform_name, is_rate_limited=False)
            elapsed_ms = int((time.time() - start_time) * 1000)
            structured_logger.log_request(
                platform=platform_name,
                product_id=product_id,
                product_url=product_url,
                success=False,
                response_time_ms=elapsed_ms,
                error_type=type(e).__name__,
                error_message=str(e),
                correlation_id=correlation_id
            )
            raise
        except Exception as e:
            self.anti_crawler.record_failure(platform_name, is_rate_limited=False)
            elapsed_ms = int((time.time() - start_time) * 1000)
            structured_logger.log_request(
                platform=platform_name,
                product_id=product_id,
                product_url=product_url,
                success=False,
                response_time_ms=elapsed_ms,
                error_type="UnexpectedError",
                error_message=str(e),
                correlation_id=correlation_id
            )
            raise PriceProviderError(f"Unexpected error: {e}")

    async def _fetch_page(self, url: str) -> str:
        """
        Fetch product page HTML (T024: Proxy Support)

        Args:
            url: Page URL

        Returns:
            HTML content

        Raises:
            NetworkError: Connection or timeout error
            RateLimitedError: Request was rate limited
            ProductNotFoundError: Product not found
        """
        headers = self.anti_crawler.get_request_headers(referer=self._get_referer(url))

        # Get proxy configuration if available (T024)
        client_kwargs = self.anti_crawler.get_httpx_client_kwargs()
        client_kwargs["timeout"] = self.timeout
        client_kwargs["follow_redirects"] = True

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(url, headers=headers)

                # Check for rate limiting
                if response.status_code == 403:
                    raise RateLimitedError(f"Request blocked (403) for {url}")

                if response.status_code == 404:
                    raise ProductNotFoundError(f"Product not found: {url}")

                if response.status_code >= 400:
                    raise NetworkError(f"HTTP error {response.status_code} for {url}")

                # Check for captcha/verification page
                content = response.text
                if self._is_captcha_page(content):
                    raise RateLimitedError(f"Captcha/verification required for {url}")

                return content

        except httpx.TimeoutException:
            raise NetworkError(f"Request timeout for {url}")
        except httpx.ConnectError as e:
            raise NetworkError(f"Connection error for {url}: {e}")
        except httpx.HTTPError as e:
            raise NetworkError(f"HTTP error for {url}: {e}")

    def _get_referer(self, url: str) -> str:
        """Get appropriate referer for URL"""
        # Return search engine as referer (looks more natural)
        return "https://www.baidu.com/s?wd=" + url.split("/")[-1][:20]

    def _is_captcha_page(self, html: str) -> bool:
        """
        Check if page is a captcha/verification page

        Args:
            html: Page HTML content

        Returns:
            True if captcha detected
        """
        captcha_indicators = [
            "验证码",
            "verify",
            "captcha",
            "robot",
            "滑动验证",
            "请完成安全验证",
            "human verification",
        ]

        html_lower = html.lower()
        return any(indicator.lower() in html_lower for indicator in captcha_indicators)

    def supports_url(self, url: str) -> bool:
        """
        Check if this provider supports the given URL

        Args:
            url: Product URL

        Returns:
            True if URL is supported
        """
        detected = detect_platform(url)
        return detected == self.platform


