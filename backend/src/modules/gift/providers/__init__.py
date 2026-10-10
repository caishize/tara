"""
Price Service Providers

Provides real e-commerce price fetching functionality.
Implements IPriceServiceProvider interface with platform-specific providers.
"""
from typing import Optional, Dict, Type

from .platform_detector import (
    Platform,
    detect_platform,
    extract_product_id,
    detect_and_extract,
    is_supported_platform,
    get_platform_display_name,
)
from .anti_crawler import (
    AntiCrawlerManager,
    AntiCrawlerConfig,
    get_anti_crawler_manager,
)
from .base import (
    BasePriceProvider,
    PriceData,
    PriceProviderError,
    NetworkError,
    RateLimitedError,
    ParseError,
    ProductNotFoundError,
    PlatformNotSupportedError,
    PlatformBlockedError,
    StructuredPriceLogger,
    structured_logger,
)
from .jd_provider import JDPriceProvider
from .taobao_provider import TaobaoPriceProvider
from .tmall_provider import TmallPriceProvider
from .pdd_provider import PDDPriceProvider

# Provider registry
PROVIDER_REGISTRY: Dict[Platform, Type[BasePriceProvider]] = {
    Platform.JD: JDPriceProvider,
    Platform.TAOBAO: TaobaoPriceProvider,
    Platform.TMALL: TmallPriceProvider,
    Platform.PDD: PDDPriceProvider,
}


class PriceServiceProvider:
    """
    Unified price service provider

    Automatically selects the appropriate provider based on URL
    """

    def __init__(
        self,
        anti_crawler: Optional[AntiCrawlerManager] = None,
        timeout: float = 10.0
    ):
        """
        Initialize price service

        Args:
            anti_crawler: Anti-crawler manager (uses default if None)
            timeout: Request timeout in seconds
        """
        self.anti_crawler = anti_crawler or get_anti_crawler_manager()
        self.timeout = timeout
        self._providers: Dict[Platform, BasePriceProvider] = {}

    def _get_provider(self, platform: Platform) -> BasePriceProvider:
        """Get or create provider for platform"""
        if platform not in self._providers:
            provider_class = PROVIDER_REGISTRY.get(platform)
            if not provider_class:
                raise PlatformNotSupportedError(
                    f"Platform {platform.value} is not supported"
                )
            self._providers[platform] = provider_class(
                anti_crawler=self.anti_crawler,
                timeout=self.timeout
            )
        return self._providers[platform]

    async def get_price(
        self,
        product_url: str,
        platform: Optional[str] = None
    ) -> PriceData:
        """
        Get current price for a product

        Args:
            product_url: Product page URL
            platform: Optional platform hint (auto-detect if None)

        Returns:
            PriceData object

        Raises:
            PlatformNotSupportedError: If platform is not supported
            NetworkError: Connection or timeout error
            RateLimitedError: Request was rate limited
            ParseError: Failed to parse price
            ProductNotFoundError: Product not found
            PlatformBlockedError: Platform temporarily blocked
        """
        # Detect platform if not provided
        if platform:
            detected_platform = Platform(platform.lower())
        else:
            detected_platform = detect_platform(product_url)

        if detected_platform == Platform.UNKNOWN:
            raise PlatformNotSupportedError(
                f"Cannot detect platform from URL: {product_url}. "
                f"Supported platforms: 京东, 淘宝, 天猫, 拼多多"
            )

        # Get appropriate provider
        provider = self._get_provider(detected_platform)

        # Fetch price
        return await provider.get_price(product_url)

    def get_platform_stats(self) -> Dict[str, Dict]:
        """Get statistics for all platforms"""
        return self.anti_crawler.get_all_stats()


def create_price_service(
    anti_crawler: Optional[AntiCrawlerManager] = None,
    timeout: float = 10.0
) -> PriceServiceProvider:
    """
    Factory function to create price service

    Args:
        anti_crawler: Anti-crawler manager (uses default if None)
        timeout: Request timeout in seconds

    Returns:
        PriceServiceProvider instance
    """
    return PriceServiceProvider(
        anti_crawler=anti_crawler,
        timeout=timeout
    )


# Import promotion configuration
from .promotion import (
    PromotionPeriod,
    PromotionManager,
    get_promotion_manager,
    is_promotion_period,
    get_current_promotion_names,
    DEFAULT_PROMOTION_PERIODS,
)

# Re-export for convenience
__all__ = [
    # Factory
    "create_price_service",
    "PriceServiceProvider",
    # Platform detection
    "Platform",
    "detect_platform",
    "extract_product_id",
    "detect_and_extract",
    "is_supported_platform",
    "get_platform_display_name",
    # Anti-crawler
    "AntiCrawlerManager",
    "AntiCrawlerConfig",
    "get_anti_crawler_manager",
    # Promotion
    "PromotionPeriod",
    "PromotionManager",
    "get_promotion_manager",
    "is_promotion_period",
    "get_current_promotion_names",
    "DEFAULT_PROMOTION_PERIODS",
    # Base classes
    "BasePriceProvider",
    "PriceData",
    # Logging
    "StructuredPriceLogger",
    "structured_logger",
    # Errors
    "PriceProviderError",
    "NetworkError",
    "RateLimitedError",
    "ParseError",
    "ProductNotFoundError",
    "PlatformNotSupportedError",
    "PlatformBlockedError",
    # Providers
    "JDPriceProvider",
    "TaobaoPriceProvider",
    "TmallPriceProvider",
    "PDDPriceProvider",
]
