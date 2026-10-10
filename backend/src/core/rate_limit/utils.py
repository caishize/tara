"""
Shared utilities for rate limiting.

Extracted to avoid duplication between middleware and decorators.
"""

from .rate_limiter import RateLimitTier


def subscription_to_tier(subscription: str) -> RateLimitTier:
    """Convert subscription level string to rate limit tier."""
    mapping = {
        "free": RateLimitTier.FREE,
        "basic": RateLimitTier.BASIC,
        "premium": RateLimitTier.PREMIUM,
        "enterprise": RateLimitTier.PREMIUM,
    }
    return mapping.get(subscription.lower(), RateLimitTier.FREE)
