"""
Anti-Crawler Strategies
Implements request throttling, User-Agent rotation, and rate limiting
"""
import random
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

# User-Agent list (Chrome, Firefox, Safari on Windows/Mac)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Mobile Chrome
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]

# Default request headers template
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
}


class RateLimitStatus(str, Enum):
    """Rate limit status for a platform"""
    NORMAL = "normal"
    THROTTLED = "throttled"
    BLOCKED = "blocked"


@dataclass
class PlatformRateLimit:
    """Rate limit state for a platform"""
    platform: str
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    blocked_until: Optional[datetime] = None
    current_delay_multiplier: float = 1.0
    total_requests: int = 0
    successful_requests: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def status(self) -> RateLimitStatus:
        """Get current rate limit status"""
        if self.blocked_until and utc_now() < self.blocked_until:
            return RateLimitStatus.BLOCKED
        if self.current_delay_multiplier > 2.0:
            return RateLimitStatus.THROTTLED
        return RateLimitStatus.NORMAL


@dataclass
class AntiCrawlerConfig:
    """
    Anti-crawler configuration (T024: Proxy Support)

    Attributes:
        base_delay_min: Minimum delay between requests (seconds)
        base_delay_max: Maximum delay between requests (seconds)
        failure_backoff_multiplier: Multiply delay on failure
        max_delay: Maximum delay (seconds)
        max_consecutive_failures: Block platform after this many failures
        block_duration_minutes: How long to block platform
        proxy_url: Optional proxy URL (reads from PRICE_PROXY_URL env var if None)
        proxy_username: Optional proxy authentication username
        proxy_password: Optional proxy authentication password
    """
    base_delay_min: float = 3.0
    base_delay_max: float = 8.0
    failure_backoff_multiplier: float = 2.0
    max_delay: float = 60.0
    max_consecutive_failures: int = 5
    block_duration_minutes: int = 60
    proxy_url: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None

    def __post_init__(self):
        """Load proxy configuration from environment if not provided"""
        import os
        if self.proxy_url is None:
            self.proxy_url = os.getenv("PRICE_PROXY_URL")
        if self.proxy_username is None:
            self.proxy_username = os.getenv("PRICE_PROXY_USERNAME")
        if self.proxy_password is None:
            self.proxy_password = os.getenv("PRICE_PROXY_PASSWORD")


class AntiCrawlerManager:
    """
    Manages anti-crawler strategies across platforms
    """

    def __init__(self, config: Optional[AntiCrawlerConfig] = None):
        """
        Initialize anti-crawler manager

        Args:
            config: Anti-crawler configuration
        """
        self.config = config or AntiCrawlerConfig()
        self._platform_states: Dict[str, PlatformRateLimit] = {}
        self._last_request_time: Optional[float] = None

    def get_random_user_agent(self) -> str:
        """Get a random User-Agent string"""
        return random.choice(USER_AGENTS)

    def get_request_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """
        Get request headers with random User-Agent

        Args:
            referer: Optional referer URL

        Returns:
            Headers dictionary
        """
        headers = DEFAULT_HEADERS.copy()
        headers["User-Agent"] = self.get_random_user_agent()

        if referer:
            headers["Referer"] = referer

        return headers

    def get_proxy_config(self) -> Optional[Dict[str, str]]:
        """
        Get proxy configuration for httpx (T024: Proxy Support)

        Returns:
            Proxy configuration dict for httpx or None if no proxy configured
        """
        if not self.config.proxy_url:
            return None

        proxy_url = self.config.proxy_url

        # Add authentication if provided
        if self.config.proxy_username and self.config.proxy_password:
            # Parse the proxy URL and insert credentials
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_url)
            netloc = f"{self.config.proxy_username}:{self.config.proxy_password}@{parsed.hostname}"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            proxy_url = urlunparse((
                parsed.scheme, netloc, parsed.path,
                parsed.params, parsed.query, parsed.fragment
            ))

        # httpx uses "all://" for all protocols
        return {"all://": proxy_url}

    def get_httpx_client_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs for httpx.AsyncClient including proxy if configured

        Returns:
            Dict with kwargs for httpx.AsyncClient
        """
        kwargs: Dict[str, Any] = {}

        proxy_config = self.get_proxy_config()
        if proxy_config:
            kwargs["proxies"] = proxy_config
            logger.debug(f"Using proxy for requests")

        return kwargs

    def get_random_delay(self, platform: Optional[str] = None) -> float:
        """
        Get random delay with platform-specific adjustments

        Args:
            platform: Optional platform identifier

        Returns:
            Delay in seconds
        """
        base_delay = random.uniform(
            self.config.base_delay_min,
            self.config.base_delay_max
        )

        # Apply platform-specific multiplier if throttled
        if platform:
            state = self._get_platform_state(platform)
            base_delay *= state.current_delay_multiplier

        # Cap at maximum delay
        return min(base_delay, self.config.max_delay)

    async def wait_before_request(self, platform: Optional[str] = None) -> float:
        """
        Wait appropriate time before making request

        Args:
            platform: Optional platform identifier

        Returns:
            Actual wait time in seconds
        """
        delay = self.get_random_delay(platform)

        # Ensure minimum time since last request
        if self._last_request_time:
            elapsed = time.time() - self._last_request_time
            if elapsed < delay:
                wait_time = delay - elapsed
                await asyncio.sleep(wait_time)
                self._last_request_time = time.time()
                return wait_time

        self._last_request_time = time.time()
        return 0.0

    def is_platform_blocked(self, platform: str) -> bool:
        """
        Check if platform is currently blocked

        Args:
            platform: Platform identifier

        Returns:
            True if blocked
        """
        state = self._get_platform_state(platform)
        return state.status == RateLimitStatus.BLOCKED

    def get_block_remaining_seconds(self, platform: str) -> Optional[float]:
        """
        Get remaining block time for platform

        Args:
            platform: Platform identifier

        Returns:
            Remaining seconds or None if not blocked
        """
        state = self._get_platform_state(platform)
        if state.blocked_until and utc_now() < state.blocked_until:
            return (state.blocked_until - utc_now()).total_seconds()
        return None

    def record_success(self, platform: str) -> None:
        """
        Record successful request

        Args:
            platform: Platform identifier
        """
        state = self._get_platform_state(platform)
        state.total_requests += 1
        state.successful_requests += 1
        state.consecutive_failures = 0
        state.current_delay_multiplier = max(1.0, state.current_delay_multiplier * 0.9)

        logger.debug(
            f"Platform {platform}: success recorded, "
            f"rate={state.success_rate:.2%}, "
            f"delay_multiplier={state.current_delay_multiplier:.2f}"
        )

    def record_failure(self, platform: str, is_rate_limited: bool = False) -> bool:
        """
        Record failed request

        Args:
            platform: Platform identifier
            is_rate_limited: Whether failure was due to rate limiting (403, captcha)

        Returns:
            True if platform is now blocked
        """
        state = self._get_platform_state(platform)
        state.total_requests += 1
        state.consecutive_failures += 1
        state.last_failure_time = utc_now()

        # Increase delay multiplier on failure
        if is_rate_limited:
            state.current_delay_multiplier *= self.config.failure_backoff_multiplier
        else:
            state.current_delay_multiplier *= 1.5

        if self.config.base_delay_min > 0:
            state.current_delay_multiplier = min(
                state.current_delay_multiplier,
                self.config.max_delay / self.config.base_delay_min,
            )

        # Block platform if too many consecutive failures
        if state.consecutive_failures >= self.config.max_consecutive_failures:
            state.blocked_until = utc_now() + timedelta(
                minutes=self.config.block_duration_minutes
            )
            logger.warning(
                f"Platform {platform} blocked for {self.config.block_duration_minutes} minutes "
                f"after {state.consecutive_failures} consecutive failures"
            )
            return True

        logger.warning(
            f"Platform {platform}: failure recorded, "
            f"consecutive={state.consecutive_failures}, "
            f"delay_multiplier={state.current_delay_multiplier:.2f}"
        )

        return False

    def get_platform_stats(self, platform: str) -> Dict[str, Any]:
        """
        Get statistics for platform

        Args:
            platform: Platform identifier

        Returns:
            Statistics dictionary
        """
        state = self._get_platform_state(platform)
        return {
            "platform": platform,
            "status": state.status.value,
            "success_rate": state.success_rate,
            "total_requests": state.total_requests,
            "successful_requests": state.successful_requests,
            "consecutive_failures": state.consecutive_failures,
            "delay_multiplier": state.current_delay_multiplier,
            "blocked_until": state.blocked_until.isoformat() if state.blocked_until else None,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all platforms"""
        return {
            platform: self.get_platform_stats(platform)
            for platform in self._platform_states
        }

    def reset_platform(self, platform: str) -> None:
        """Reset rate limit state for platform"""
        if platform in self._platform_states:
            del self._platform_states[platform]
        logger.info(f"Platform {platform} rate limit state reset")

    def _get_platform_state(self, platform: str) -> PlatformRateLimit:
        """Get or create rate limit state for platform"""
        if platform not in self._platform_states:
            self._platform_states[platform] = PlatformRateLimit(platform=platform)
        return self._platform_states[platform]


# Global instance for convenience
_default_manager: Optional[AntiCrawlerManager] = None


def get_anti_crawler_manager() -> AntiCrawlerManager:
    """Get or create default anti-crawler manager"""
    global _default_manager
    if _default_manager is None:
        _default_manager = AntiCrawlerManager()
    return _default_manager
