"""
Rate Limiter - Redis-based rate limiting with tiered limits.

Uses sliding window algorithm for accurate rate limiting.
Supports different tiers for unauthenticated, free, basic, and premium users.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from ..utils.timezone import utc_now
from enum import Enum
from typing import Dict, Optional, Tuple
from uuid import uuid4

from ...config.settings import settings
from ..cache import redis_client


logger = logging.getLogger(__name__)


class RateLimitTier(str, Enum):
    """Rate limit tiers based on user subscription level."""
    UNAUTHENTICATED = "unauthenticated"
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None
    limit: int = 0
    current: int = 0


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for a rate limit tier."""
    requests_per_minute: int
    requests_per_hour: int
    burst_allowance: int = 5  # Extra requests allowed in burst


class RedisRateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Features:
    - Per-minute and per-hour limits
    - Tiered limits based on user subscription
    - Endpoint-specific overrides
    - Sliding window for accurate counting
    """

    # Endpoint-specific multipliers (1.0 = normal, 0.5 = half rate, 2.0 = double rate)
    ENDPOINT_MULTIPLIERS: Dict[str, float] = {
        "/api/v1/chat": 0.5,  # AI chat endpoints are more expensive
        "/api/v1/research": 0.3,  # Research is very expensive
        "/health": 10.0,  # Health checks should be very permissive
        "/metrics": 10.0,
    }

    @staticmethod
    def _tier_limits_from_settings() -> Dict["RateLimitTier", RateLimitConfig]:
        """Build tier limits from env-driven settings (no hardcoded values)."""
        return {
            RateLimitTier.UNAUTHENTICATED: RateLimitConfig(
                requests_per_minute=settings.rate_limit_per_minute_unauthenticated,
                requests_per_hour=settings.rate_limit_unauth_per_hour,
                burst_allowance=settings.rate_limit_unauth_burst,
            ),
            RateLimitTier.FREE: RateLimitConfig(
                requests_per_minute=settings.rate_limit_free_per_minute,
                requests_per_hour=settings.rate_limit_free_per_hour,
                burst_allowance=settings.rate_limit_free_burst,
            ),
            RateLimitTier.BASIC: RateLimitConfig(
                requests_per_minute=settings.rate_limit_basic_per_minute,
                requests_per_hour=settings.rate_limit_basic_per_hour,
                burst_allowance=settings.rate_limit_basic_burst,
            ),
            RateLimitTier.PREMIUM: RateLimitConfig(
                requests_per_minute=settings.rate_limit_premium_per_minute,
                requests_per_hour=settings.rate_limit_premium_per_hour,
                burst_allowance=settings.rate_limit_premium_burst,
            ),
        }

    # Key prefix for Redis
    KEY_PREFIX = "rate_limit"

    # Window sizes in seconds
    MINUTE_WINDOW = 60
    HOUR_WINDOW = 3600

    def __init__(self):
        self._redis = redis_client
        self._cached_tier_limits = self._tier_limits_from_settings()

    def _get_config(self, tier: RateLimitTier) -> RateLimitConfig:
        """Get rate limit config for a tier."""
        return self._cached_tier_limits.get(
            tier, self._cached_tier_limits[RateLimitTier.UNAUTHENTICATED]
        )

    def _get_endpoint_multiplier(self, endpoint: str) -> float:
        """Get rate multiplier for an endpoint."""
        # Check for exact match first
        if endpoint in self.ENDPOINT_MULTIPLIERS:
            return self.ENDPOINT_MULTIPLIERS[endpoint]

        # Check for prefix matches
        for path_prefix, multiplier in self.ENDPOINT_MULTIPLIERS.items():
            if endpoint.startswith(path_prefix):
                return multiplier

        return 1.0

    def _calculate_effective_limits(
        self,
        tier: RateLimitTier,
        endpoint: str,
    ) -> Tuple[int, int]:
        """Calculate effective limits considering endpoint multiplier."""
        config = self._get_config(tier)
        multiplier = self._get_endpoint_multiplier(endpoint)

        # Apply multiplier (higher multiplier = more requests allowed)
        effective_per_minute = int(config.requests_per_minute * multiplier)
        effective_per_hour = int(config.requests_per_hour * multiplier)

        # Ensure at least 1 request is allowed
        return max(1, effective_per_minute), max(1, effective_per_hour)

    # Lua script for atomic check-and-record to prevent TOCTOU race conditions.
    # Cleans expired entries, counts current requests, and conditionally adds
    # the new request — all in a single atomic Redis operation.
    _RATE_LIMIT_SCRIPT = """
    local minute_key = KEYS[1]
    local hour_key = KEYS[2]
    local now_ts = tonumber(ARGV[1])
    local minute_window_start = tonumber(ARGV[2])
    local hour_window_start = tonumber(ARGV[3])
    local minute_limit = tonumber(ARGV[4])
    local hour_limit = tonumber(ARGV[5])
    local minute_expire = tonumber(ARGV[6])
    local hour_expire = tonumber(ARGV[7])

    -- Clean expired entries
    redis.call('ZREMRANGEBYSCORE', minute_key, 0, minute_window_start)
    redis.call('ZREMRANGEBYSCORE', hour_key, 0, hour_window_start)

    -- Count current requests
    local minute_count = redis.call('ZCARD', minute_key)
    local hour_count = redis.call('ZCARD', hour_key)

    -- Check limits
    if minute_count >= minute_limit or hour_count >= hour_limit then
        return {0, minute_count, hour_count}
    end

    -- Record the request
    redis.call('ZADD', minute_key, now_ts, ARGV[8])
    redis.call('ZADD', hour_key, now_ts, ARGV[8])
    redis.call('EXPIRE', minute_key, minute_expire)
    redis.call('EXPIRE', hour_key, hour_expire)

    return {1, minute_count, hour_count}
    """

    async def check_rate_limit(
        self,
        identifier: str,
        tier: RateLimitTier,
        endpoint: str = "/",
    ) -> RateLimitResult:
        """
        Check if a request is allowed under rate limits.

        Uses sliding window algorithm with Redis sorted sets.
        All check-and-record operations are atomic via a Lua script
        to prevent TOCTOU race conditions.

        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            tier: User's rate limit tier
            endpoint: API endpoint being accessed

        Returns:
            RateLimitResult indicating if request is allowed
        """
        now = utc_now()
        now_ts = now.timestamp()

        # Calculate effective limits
        limit_per_minute, limit_per_hour = self._calculate_effective_limits(tier, endpoint)
        config = self._get_config(tier)

        # Generate Redis keys
        minute_key = f"{self.KEY_PREFIX}:{identifier}:minute"
        hour_key = f"{self.KEY_PREFIX}:{identifier}:hour"

        # Limits including burst allowance
        minute_limit_with_burst = limit_per_minute + config.burst_allowance
        hour_limit_with_burst = limit_per_hour + config.burst_allowance

        try:
            # Atomic check-and-record via Lua script
            # Use a unique member ID to avoid ZADD collisions under concurrent load
            member_id = f"{now_ts}:{uuid4().hex[:8]}"

            result = await self._redis.client.eval(
                self._RATE_LIMIT_SCRIPT,
                2,  # number of keys
                minute_key,
                hour_key,
                str(now_ts),
                str(now_ts - self.MINUTE_WINDOW),
                str(now_ts - self.HOUR_WINDOW),
                str(minute_limit_with_burst),
                str(hour_limit_with_burst),
                str(self.MINUTE_WINDOW + 10),
                str(self.HOUR_WINDOW + 10),
                member_id,
            )

            allowed = bool(result[0])
            minute_count = int(result[1])
            hour_count = int(result[2])

            if not allowed:
                # Determine which limit was hit for retry-after calculation
                minute_exceeded = minute_count >= minute_limit_with_burst

                if minute_exceeded:
                    oldest = await self._redis.client.zrange(minute_key, 0, 0, withscores=True)
                    if oldest:
                        oldest_ts = oldest[0][1]
                        retry_after = int(self.MINUTE_WINDOW - (now_ts - oldest_ts)) + 1
                    else:
                        retry_after = self.MINUTE_WINDOW
                    limit = limit_per_minute
                    current = minute_count
                else:
                    oldest = await self._redis.client.zrange(hour_key, 0, 0, withscores=True)
                    if oldest:
                        oldest_ts = oldest[0][1]
                        retry_after = int(self.HOUR_WINDOW - (now_ts - oldest_ts)) + 1
                    else:
                        retry_after = self.HOUR_WINDOW
                    limit = limit_per_hour
                    current = hour_count

                reset_at = datetime.fromtimestamp(now_ts + retry_after, tz=timezone.utc)

                logger.warning(
                    "Rate limit exceeded: identifier=%s, tier=%s, endpoint=%s, "
                    "minute_count=%d, hour_count=%d",
                    identifier, tier, endpoint, minute_count, hour_count,
                )

                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                    limit=limit,
                    current=current,
                )

            # Request allowed
            remaining_minute = limit_per_minute - minute_count - 1
            remaining_hour = limit_per_hour - hour_count - 1
            remaining = min(remaining_minute, remaining_hour)
            reset_at = datetime.fromtimestamp(now_ts + self.MINUTE_WINDOW, tz=timezone.utc)

            return RateLimitResult(
                allowed=True,
                remaining=max(0, remaining),
                reset_at=reset_at,
                limit=limit_per_minute,
                current=minute_count + 1,
            )

        except Exception as e:
            # On Redis error, allow request but log warning
            logger.error("Rate limiter error, allowing request: %s", e)
            return RateLimitResult(
                allowed=True,
                remaining=0,
                reset_at=utc_now(),
                limit=0,
                current=0,
            )

    async def get_current_usage(
        self,
        identifier: str,
    ) -> dict:
        """Get current rate limit usage for an identifier."""
        now_ts = utc_now().timestamp()

        minute_key = f"{self.KEY_PREFIX}:{identifier}:minute"
        hour_key = f"{self.KEY_PREFIX}:{identifier}:hour"

        try:
            pipe = self._redis.client.pipeline()

            # Clean and count
            pipe.zremrangebyscore(minute_key, 0, now_ts - self.MINUTE_WINDOW)
            pipe.zremrangebyscore(hour_key, 0, now_ts - self.HOUR_WINDOW)
            pipe.zcard(minute_key)
            pipe.zcard(hour_key)

            results = await pipe.execute()

            return {
                "minute_count": results[2],
                "hour_count": results[3],
            }
        except Exception as e:
            logger.error("Error getting rate limit usage: %s", e)
            return {"minute_count": 0, "hour_count": 0}

    async def reset_limits(self, identifier: str) -> bool:
        """Reset rate limits for an identifier (admin use)."""
        minute_key = f"{self.KEY_PREFIX}:{identifier}:minute"
        hour_key = f"{self.KEY_PREFIX}:{identifier}:hour"

        try:
            await self._redis.client.delete(minute_key, hour_key)
            logger.info("Rate limits reset for: %s", identifier)
            return True
        except Exception as e:
            logger.error("Error resetting rate limits: %s", e)
            return False


# Module-level singleton for the rate limiter.
# This is used instead of FastAPI Depends() because middleware and decorators
# both need access and middleware runs outside the dependency injection scope.
_rate_limiter: Optional[RedisRateLimiter] = None


def get_rate_limiter() -> RedisRateLimiter:
    """Get or create the module-level rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RedisRateLimiter()
    return _rate_limiter
