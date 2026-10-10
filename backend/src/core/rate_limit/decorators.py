"""
Rate Limit Decorators - Function-level rate limiting for specific endpoints.
"""

import functools
import logging
from typing import Callable, Optional

from fastapi import HTTPException, Request, status

from .rate_limiter import RateLimitTier, get_rate_limiter
from .utils import subscription_to_tier


logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit exceeded."""

    def __init__(
        self,
        retry_after: int,
        detail: str = "Rate limit exceeded",
    ):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(
    tier_override: Optional[RateLimitTier] = None,
    custom_identifier: Optional[Callable[[Request], str]] = None,
):
    """
    Decorator for applying rate limits to specific endpoints.

    Usage:
        @router.get("/expensive-operation")
        @rate_limit(tier_override=RateLimitTier.PREMIUM)
        async def expensive_operation(request: Request):
            ...

    Args:
        tier_override: Override the user's tier for this endpoint
        custom_identifier: Custom function to generate rate limit identifier
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the request object in args or kwargs
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if request is None:
                # No request found, skip rate limiting
                logger.warning(
                    "No Request object found in %s, skipping rate limit",
                    func.__name__,
                )
                return await func(*args, **kwargs)

            # Get identifier
            if custom_identifier:
                identifier = custom_identifier(request)
            else:
                # Default: use user_id if authenticated, else IP
                user = getattr(request.state, "user", None)
                if user and hasattr(user, "id"):
                    identifier = f"user:{user.id}"
                else:
                    identifier = f"ip:{request.client.host if request.client else 'unknown'}"

            # Get tier
            if tier_override:
                tier = tier_override
            else:
                user = getattr(request.state, "user", None)
                if user:
                    # Get tier from user's subscription level
                    subscription = getattr(user, "subscription_level", "free")
                    tier = subscription_to_tier(subscription)
                else:
                    tier = RateLimitTier.UNAUTHENTICATED

            # Check rate limit
            limiter = get_rate_limiter()
            result = await limiter.check_rate_limit(
                identifier=identifier,
                tier=tier,
                endpoint=request.url.path,
            )

            if not result.allowed:
                raise RateLimitExceeded(
                    retry_after=result.retry_after or 60,
                    detail=f"Rate limit exceeded. Try again in {result.retry_after} seconds.",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


