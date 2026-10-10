"""
Retry Policies

Defines retry strategies for failed job executions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay_seconds: Base delay between retries
        max_delay_seconds: Maximum delay (for exponential backoff)
        jitter: Whether to add random jitter to delays
    """
    max_retries: int = 3
    base_delay_seconds: int = 60
    max_delay_seconds: int = 3600  # 1 hour max
    jitter: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")
        if self.base_delay_seconds < 0:
            raise ValueError(f"base_delay_seconds must be non-negative, got {self.base_delay_seconds}")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                f"max_delay_seconds ({self.max_delay_seconds}) must be >= "
                f"base_delay_seconds ({self.base_delay_seconds})"
            )


class RetryPolicy(ABC):
    """Abstract base class for retry policies."""

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize with configuration."""
        self.config = config or RetryConfig()

    @abstractmethod
    def get_delay(self, attempt: int) -> int:
        """
        Get the delay in seconds before the next retry.

        Args:
            attempt: The retry attempt number (1-indexed)

        Returns:
            Delay in seconds before the next retry
        """
        pass

    def should_retry(self, attempt: int) -> bool:
        """
        Check if another retry should be attempted.

        Args:
            attempt: The current attempt number (1-indexed)

        Returns:
            True if another retry should be attempted
        """
        return attempt <= self.config.max_retries

    def _apply_jitter(self, delay: int) -> int:
        """Apply random jitter to delay if configured."""
        if not self.config.jitter:
            return delay

        import random
        # Add +/- 10% jitter
        jitter_range = delay * 0.1
        jitter = random.uniform(-jitter_range, jitter_range)
        return max(1, int(delay + jitter))

    def _cap_delay(self, delay: int) -> int:
        """Cap delay at maximum configured value."""
        return min(delay, self.config.max_delay_seconds)


class FixedRetryPolicy(RetryPolicy):
    """
    Fixed interval retry policy.

    Always waits the same amount of time between retries.
    """

    def get_delay(self, attempt: int) -> int:
        """Get fixed delay for any attempt."""
        delay = self.config.base_delay_seconds
        delay = self._cap_delay(delay)
        return self._apply_jitter(delay)


class ExponentialRetryPolicy(RetryPolicy):
    """
    Exponential backoff retry policy.

    Delay doubles with each attempt: base * 2^(attempt-1)
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        multiplier: float = 2.0
    ):
        """
        Initialize exponential retry policy.

        Args:
            config: Retry configuration
            multiplier: Multiplier for exponential growth (default 2.0)
        """
        super().__init__(config)
        self.multiplier = multiplier

    def get_delay(self, attempt: int) -> int:
        """
        Get exponentially increasing delay.

        Delay = base * multiplier^(attempt-1)
        """
        delay = int(self.config.base_delay_seconds * (self.multiplier ** (attempt - 1)))
        delay = self._cap_delay(delay)
        return self._apply_jitter(delay)


class LinearRetryPolicy(RetryPolicy):
    """
    Linear backoff retry policy.

    Delay increases linearly with each attempt: base * attempt
    """

    def get_delay(self, attempt: int) -> int:
        """
        Get linearly increasing delay.

        Delay = base * attempt
        """
        delay = self.config.base_delay_seconds * attempt
        delay = self._cap_delay(delay)
        return self._apply_jitter(delay)


class NoRetryPolicy(RetryPolicy):
    """
    No retry policy.

    Never retries - fails immediately.
    """

    def __init__(self):
        """Initialize with zero retries."""
        super().__init__(RetryConfig(max_retries=0))

    def get_delay(self, attempt: int) -> int:
        """No delay needed since we never retry."""
        return 0

    def should_retry(self, attempt: int) -> bool:
        """Never retry."""
        return False
