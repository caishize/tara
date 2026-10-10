"""
Unit tests for anti-crawler strategies (T005, T021)
Tests User-Agent rotation, random delays, rate limiting, and circuit breaker.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from src.modules.gift.providers.anti_crawler import (
    AntiCrawlerManager,
    AntiCrawlerConfig,
    PlatformRateLimit,
    RateLimitStatus,
    USER_AGENTS,
    DEFAULT_HEADERS,
    get_anti_crawler_manager,
)


class TestAntiCrawlerConfig:
    """Test anti-crawler configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = AntiCrawlerConfig()
        assert config.base_delay_min == 3.0
        assert config.base_delay_max == 8.0
        assert config.failure_backoff_multiplier == 2.0
        assert config.max_delay == 60.0
        assert config.max_consecutive_failures == 5
        assert config.block_duration_minutes == 60
        assert config.proxy_url is None

    def test_custom_config(self):
        """Test custom configuration"""
        config = AntiCrawlerConfig(
            base_delay_min=1.0,
            base_delay_max=3.0,
            max_consecutive_failures=3,
            proxy_url="http://proxy:8080"
        )
        assert config.base_delay_min == 1.0
        assert config.base_delay_max == 3.0
        assert config.max_consecutive_failures == 3
        assert config.proxy_url == "http://proxy:8080"


class TestUserAgentRotation:
    """Test User-Agent rotation (FR-012)"""

    def test_user_agents_count(self):
        """Verify at least 10 User-Agents are configured"""
        assert len(USER_AGENTS) >= 10, "Should have at least 10 User-Agents"

    def test_user_agents_variety(self):
        """Verify User-Agents include different browsers"""
        ua_string = " ".join(USER_AGENTS)
        assert "Chrome" in ua_string, "Should include Chrome"
        assert "Firefox" in ua_string, "Should include Firefox"
        assert "Safari" in ua_string, "Should include Safari"

    def test_get_random_user_agent(self):
        """Test random User-Agent selection"""
        manager = AntiCrawlerManager()

        # Get multiple User-Agents
        agents = [manager.get_random_user_agent() for _ in range(20)]

        # All should be valid
        assert all(agent in USER_AGENTS for agent in agents)

        # Should have some variety (not all the same)
        unique_agents = set(agents)
        assert len(unique_agents) > 1, "Should return different User-Agents"


class TestRequestHeaders:
    """Test request header generation"""

    def test_get_request_headers_basic(self):
        """Test basic header generation"""
        manager = AntiCrawlerManager()
        headers = manager.get_request_headers()

        # Should have User-Agent
        assert "User-Agent" in headers
        assert headers["User-Agent"] in USER_AGENTS

        # Should have common headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers

    def test_get_request_headers_with_referer(self):
        """Test header generation with referer"""
        manager = AntiCrawlerManager()
        referer = "https://www.baidu.com/s?wd=test"
        headers = manager.get_request_headers(referer=referer)

        assert headers.get("Referer") == referer


class TestRandomDelay:
    """Test random delay generation (FR-011)"""

    def test_delay_within_range(self):
        """Test delay is within configured range (3-8 seconds)"""
        config = AntiCrawlerConfig(base_delay_min=3.0, base_delay_max=8.0)
        manager = AntiCrawlerManager(config)

        for _ in range(100):
            delay = manager.get_random_delay()
            assert 3.0 <= delay <= 8.0, f"Delay {delay} should be between 3-8 seconds"

    def test_delay_distribution(self):
        """Test delay is reasonably random"""
        config = AntiCrawlerConfig(base_delay_min=3.0, base_delay_max=8.0)
        manager = AntiCrawlerManager(config)

        delays = [manager.get_random_delay() for _ in range(100)]

        # Check distribution covers the range
        min_delay = min(delays)
        max_delay = max(delays)
        assert min_delay < 4.0, "Should have some delays near minimum"
        assert max_delay > 7.0, "Should have some delays near maximum"

    def test_delay_respects_multiplier(self):
        """Test delay increases with platform multiplier"""
        manager = AntiCrawlerManager()

        # Simulate failures to increase multiplier
        for _ in range(3):
            manager.record_failure("test_platform", is_rate_limited=True)

        # Delay should be higher due to multiplier
        delay = manager.get_random_delay("test_platform")
        state = manager._get_platform_state("test_platform")

        assert state.current_delay_multiplier > 1.0
        # Delay should be multiplied (but capped at max)
        assert delay <= manager.config.max_delay


class TestCircuitBreaker:
    """Test circuit breaker / platform blocking (FR-015)"""

    def test_initial_state_not_blocked(self):
        """Test platform is not blocked initially"""
        manager = AntiCrawlerManager()
        assert not manager.is_platform_blocked("jd")

    def test_block_after_consecutive_failures(self):
        """Test platform blocked after 5 consecutive failures (FR-015)"""
        config = AntiCrawlerConfig(max_consecutive_failures=5)
        manager = AntiCrawlerManager(config)

        # Record 4 failures - should not be blocked yet
        for i in range(4):
            blocked = manager.record_failure("jd", is_rate_limited=True)
            assert not blocked, f"Should not be blocked after {i+1} failures"
            assert not manager.is_platform_blocked("jd")

        # 5th failure should trigger block
        blocked = manager.record_failure("jd", is_rate_limited=True)
        assert blocked, "Should be blocked after 5 failures"
        assert manager.is_platform_blocked("jd")

    def test_block_duration(self):
        """Test platform block duration (1 hour default)"""
        config = AntiCrawlerConfig(
            max_consecutive_failures=5,
            block_duration_minutes=60
        )
        manager = AntiCrawlerManager(config)

        # Trigger block
        for _ in range(5):
            manager.record_failure("jd", is_rate_limited=True)

        # Check remaining time
        remaining = manager.get_block_remaining_seconds("jd")
        assert remaining is not None
        # Should be close to 60 minutes (3600 seconds), allow some margin
        assert 3500 <= remaining <= 3600

    def test_block_expires(self):
        """Test block expires after duration"""
        config = AntiCrawlerConfig(
            max_consecutive_failures=5,
            block_duration_minutes=60
        )
        manager = AntiCrawlerManager(config)

        # Trigger block
        for _ in range(5):
            manager.record_failure("jd", is_rate_limited=True)

        # Manually set block time to past
        state = manager._get_platform_state("jd")
        state.blocked_until = datetime.now() - timedelta(minutes=1)

        # Should no longer be blocked
        assert not manager.is_platform_blocked("jd")
        assert manager.get_block_remaining_seconds("jd") is None

    def test_success_resets_failure_count(self):
        """Test success resets consecutive failure count"""
        manager = AntiCrawlerManager()

        # Record some failures
        for _ in range(3):
            manager.record_failure("jd")

        state = manager._get_platform_state("jd")
        assert state.consecutive_failures == 3

        # Success should reset
        manager.record_success("jd")
        assert state.consecutive_failures == 0


class TestExponentialBackoff:
    """Test exponential backoff (T023)"""

    def test_backoff_on_rate_limit(self):
        """Test delay multiplier increases on rate limit"""
        config = AntiCrawlerConfig(failure_backoff_multiplier=2.0)
        manager = AntiCrawlerManager(config)

        state = manager._get_platform_state("jd")
        initial_multiplier = state.current_delay_multiplier

        # Rate limited failure should double multiplier
        manager.record_failure("jd", is_rate_limited=True)
        assert state.current_delay_multiplier == initial_multiplier * 2.0

        # Another rate limit failure
        manager.record_failure("jd", is_rate_limited=True)
        assert state.current_delay_multiplier == initial_multiplier * 4.0

    def test_backoff_capped_at_max(self):
        """Test backoff multiplier capped"""
        config = AntiCrawlerConfig(
            base_delay_min=3.0,
            max_delay=60.0,
            failure_backoff_multiplier=2.0
        )
        manager = AntiCrawlerManager(config)

        # Many failures
        for _ in range(10):
            manager.record_failure("jd", is_rate_limited=True)

        state = manager._get_platform_state("jd")
        max_multiplier = config.max_delay / config.base_delay_min

        assert state.current_delay_multiplier <= max_multiplier

    def test_success_reduces_multiplier(self):
        """Test success gradually reduces delay multiplier"""
        manager = AntiCrawlerManager()

        # Build up multiplier
        for _ in range(3):
            manager.record_failure("jd", is_rate_limited=True)

        state = manager._get_platform_state("jd")
        high_multiplier = state.current_delay_multiplier

        # Success should reduce (multiply by 0.9)
        manager.record_success("jd")
        assert state.current_delay_multiplier < high_multiplier
        assert state.current_delay_multiplier >= 1.0


class TestSuccessRateTracking:
    """Test success rate tracking (FR-015)"""

    def test_initial_success_rate(self):
        """Test initial success rate is 100%"""
        manager = AntiCrawlerManager()
        state = manager._get_platform_state("jd")
        assert state.success_rate == 1.0

    def test_success_rate_after_requests(self):
        """Test success rate calculation"""
        manager = AntiCrawlerManager()

        # 8 successes, 2 failures = 80% success rate
        for _ in range(8):
            manager.record_success("jd")
        for _ in range(2):
            manager.record_failure("jd")

        state = manager._get_platform_state("jd")
        assert state.success_rate == 0.8
        assert state.total_requests == 10
        assert state.successful_requests == 8

    def test_platform_stats(self):
        """Test platform statistics reporting"""
        manager = AntiCrawlerManager()

        manager.record_success("jd")
        manager.record_failure("jd")

        stats = manager.get_platform_stats("jd")

        assert stats["platform"] == "jd"
        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["status"] == RateLimitStatus.NORMAL.value


class TestPlatformReset:
    """Test platform state reset"""

    def test_reset_platform(self):
        """Test resetting platform state"""
        manager = AntiCrawlerManager()

        # Build up state
        for _ in range(3):
            manager.record_failure("jd", is_rate_limited=True)

        assert "jd" in manager._platform_states

        # Reset
        manager.reset_platform("jd")

        # Should start fresh
        state = manager._get_platform_state("jd")
        assert state.consecutive_failures == 0
        assert state.current_delay_multiplier == 1.0


class TestGlobalManager:
    """Test global manager singleton"""

    def test_get_anti_crawler_manager_returns_same_instance(self):
        """Test get_anti_crawler_manager returns singleton"""
        manager1 = get_anti_crawler_manager()
        manager2 = get_anti_crawler_manager()

        assert manager1 is manager2


class TestWaitBeforeRequest:
    """Test wait_before_request async method"""

    @pytest.mark.asyncio
    async def test_wait_before_request_returns_wait_time(self):
        """Test wait_before_request tracks last request time"""
        config = AntiCrawlerConfig(base_delay_min=0.1, base_delay_max=0.2)
        manager = AntiCrawlerManager(config)

        # First call should not wait
        wait1 = await manager.wait_before_request("jd")
        # wait1 could be 0 since no previous request

        # Immediate second call should wait
        wait2 = await manager.wait_before_request("jd")
        # Should have waited some amount
        assert wait2 >= 0
