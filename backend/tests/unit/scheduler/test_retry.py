"""
Tests for RetryPolicy classes.
"""
import pytest
from unittest.mock import patch

from src.core.scheduler.retry import (
    RetryConfig,
    RetryPolicy,
    FixedRetryPolicy,
    ExponentialRetryPolicy,
    LinearRetryPolicy,
    NoRetryPolicy,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay_seconds == 60
        assert config.max_delay_seconds == 3600
        assert config.jitter is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay_seconds=30,
            max_delay_seconds=1800,
            jitter=False
        )

        assert config.max_retries == 5
        assert config.base_delay_seconds == 30
        assert config.max_delay_seconds == 1800
        assert config.jitter is False

    def test_validation_negative_retries(self):
        """Test that negative max_retries raises ValueError."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            RetryConfig(max_retries=-1)

    def test_validation_negative_base_delay(self):
        """Test that negative base_delay raises ValueError."""
        with pytest.raises(ValueError, match="base_delay_seconds must be non-negative"):
            RetryConfig(base_delay_seconds=-1)

    def test_validation_max_less_than_base(self):
        """Test that max_delay < base_delay raises ValueError."""
        with pytest.raises(ValueError, match="max_delay_seconds.*must be >= base_delay_seconds"):
            RetryConfig(base_delay_seconds=100, max_delay_seconds=50)

    def test_zero_retries_allowed(self):
        """Test that zero retries is valid."""
        config = RetryConfig(max_retries=0)
        assert config.max_retries == 0

    def test_zero_delay_allowed(self):
        """Test that zero delay is valid."""
        config = RetryConfig(base_delay_seconds=0, max_delay_seconds=0)
        assert config.base_delay_seconds == 0


class TestFixedRetryPolicy:
    """Tests for FixedRetryPolicy."""

    def test_fixed_delay(self):
        """Test that delay is always the same."""
        config = RetryConfig(base_delay_seconds=30, jitter=False)
        policy = FixedRetryPolicy(config)

        assert policy.get_delay(1) == 30
        assert policy.get_delay(2) == 30
        assert policy.get_delay(3) == 30
        assert policy.get_delay(10) == 30

    def test_should_retry(self):
        """Test should_retry based on max_retries."""
        config = RetryConfig(max_retries=3)
        policy = FixedRetryPolicy(config)

        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is True
        assert policy.should_retry(4) is False

    def test_delay_cap(self):
        """Test that delay capping is validated in config.

        The cap is enforced during config creation - base must be <= max.
        For FixedRetryPolicy, the delay is always base_delay, so capping
        happens via config validation, not during get_delay().
        """
        # This should raise since base > max is not allowed
        with pytest.raises(ValueError):
            RetryConfig(base_delay_seconds=5000, max_delay_seconds=1000, jitter=False)

        # With valid config, delay equals base
        config = RetryConfig(base_delay_seconds=100, max_delay_seconds=1000, jitter=False)
        policy = FixedRetryPolicy(config)
        assert policy.get_delay(1) == 100

    def test_jitter_applies(self):
        """Test that jitter is applied when enabled."""
        config = RetryConfig(base_delay_seconds=100, jitter=True)
        policy = FixedRetryPolicy(config)

        # With jitter, delays should vary within +/- 10%
        delays = [policy.get_delay(1) for _ in range(100)]

        # Not all should be exactly 100
        assert not all(d == 100 for d in delays)

        # All should be within range (90-110)
        assert all(90 <= d <= 110 for d in delays)

    def test_no_jitter(self):
        """Test that jitter is not applied when disabled."""
        config = RetryConfig(base_delay_seconds=100, jitter=False)
        policy = FixedRetryPolicy(config)

        delays = [policy.get_delay(1) for _ in range(10)]
        assert all(d == 100 for d in delays)


class TestExponentialRetryPolicy:
    """Tests for ExponentialRetryPolicy."""

    def test_exponential_growth(self):
        """Test that delay grows exponentially."""
        config = RetryConfig(base_delay_seconds=10, max_delay_seconds=10000, jitter=False)
        policy = ExponentialRetryPolicy(config)

        # delay = base * 2^(attempt-1)
        assert policy.get_delay(1) == 10    # 10 * 2^0 = 10
        assert policy.get_delay(2) == 20    # 10 * 2^1 = 20
        assert policy.get_delay(3) == 40    # 10 * 2^2 = 40
        assert policy.get_delay(4) == 80    # 10 * 2^3 = 80

    def test_custom_multiplier(self):
        """Test custom multiplier for exponential growth."""
        config = RetryConfig(base_delay_seconds=10, max_delay_seconds=10000, jitter=False)
        policy = ExponentialRetryPolicy(config, multiplier=3.0)

        # delay = base * 3^(attempt-1)
        assert policy.get_delay(1) == 10    # 10 * 3^0 = 10
        assert policy.get_delay(2) == 30    # 10 * 3^1 = 30
        assert policy.get_delay(3) == 90    # 10 * 3^2 = 90

    def test_delay_capped(self):
        """Test that exponential delay is capped."""
        config = RetryConfig(base_delay_seconds=100, max_delay_seconds=500, jitter=False)
        policy = ExponentialRetryPolicy(config)

        # Without cap: 100, 200, 400, 800, 1600
        assert policy.get_delay(1) == 100
        assert policy.get_delay(2) == 200
        assert policy.get_delay(3) == 400
        assert policy.get_delay(4) == 500  # Capped at 500
        assert policy.get_delay(5) == 500  # Still capped

    def test_should_retry(self):
        """Test should_retry follows config."""
        config = RetryConfig(max_retries=2)
        policy = ExponentialRetryPolicy(config)

        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is False


class TestLinearRetryPolicy:
    """Tests for LinearRetryPolicy."""

    def test_linear_growth(self):
        """Test that delay grows linearly."""
        config = RetryConfig(base_delay_seconds=30, max_delay_seconds=10000, jitter=False)
        policy = LinearRetryPolicy(config)

        # delay = base * attempt
        assert policy.get_delay(1) == 30    # 30 * 1
        assert policy.get_delay(2) == 60    # 30 * 2
        assert policy.get_delay(3) == 90    # 30 * 3
        assert policy.get_delay(4) == 120   # 30 * 4

    def test_delay_capped(self):
        """Test that linear delay is capped."""
        config = RetryConfig(base_delay_seconds=100, max_delay_seconds=300, jitter=False)
        policy = LinearRetryPolicy(config)

        assert policy.get_delay(1) == 100
        assert policy.get_delay(2) == 200
        assert policy.get_delay(3) == 300
        assert policy.get_delay(4) == 300  # Capped
        assert policy.get_delay(10) == 300  # Still capped


class TestNoRetryPolicy:
    """Tests for NoRetryPolicy."""

    def test_never_retries(self):
        """Test that NoRetryPolicy never allows retries."""
        policy = NoRetryPolicy()

        assert policy.should_retry(1) is False
        assert policy.should_retry(0) is False

    def test_zero_delay(self):
        """Test that delay is always zero."""
        policy = NoRetryPolicy()

        assert policy.get_delay(1) == 0
        assert policy.get_delay(100) == 0

    def test_config_is_zero_retries(self):
        """Test that config has max_retries=0."""
        policy = NoRetryPolicy()
        assert policy.config.max_retries == 0


class TestJitterBehavior:
    """Tests for jitter behavior across policies."""

    def test_jitter_minimum_is_one(self):
        """Test that jitter never produces delay less than 1."""
        config = RetryConfig(base_delay_seconds=1, jitter=True)
        policy = FixedRetryPolicy(config)

        # Even with jitter, delay should be at least 1
        for _ in range(100):
            assert policy.get_delay(1) >= 1

    def test_jitter_range(self):
        """Test that jitter stays within +/- 10%."""
        config = RetryConfig(base_delay_seconds=1000, jitter=True)
        policy = FixedRetryPolicy(config)

        delays = [policy.get_delay(1) for _ in range(1000)]

        # Should be within 900-1100 range
        assert all(900 <= d <= 1100 for d in delays)

        # Should have some variation
        assert len(set(delays)) > 1
