"""
Rate Limit Middleware - Global rate limiting for all HTTP requests.

Applies rate limiting based on user tier and endpoint.
Adds X-RateLimit-* headers to responses.
"""

import logging
from typing import Dict, FrozenSet, Set, Tuple

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ...config.settings import settings
from .rate_limiter import RateLimitTier, get_rate_limiter
from .utils import subscription_to_tier


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies rate limiting to all requests.

    Features:
    - Automatic tier detection from user authentication
    - X-RateLimit-* response headers
    - Exempt paths for health checks, metrics, etc.
    - IP-based limiting for unauthenticated requests
    """

    # Paths that are exempt from rate limiting
    EXEMPT_PATHS: Set[str] = {
        "/health",
        "/health/db",
        "/health/redis",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    }

    # Path prefixes that are exempt
    EXEMPT_PREFIXES: Tuple[str, ...] = (
        "/static/",
        "/assets/",
    )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process the request with rate limiting."""

        # Skip rate limiting in development when auth is disabled
        if not settings.strict_auth_enabled and settings.environment == "development":
            return await call_next(request)

        # Check if path is exempt
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Get identifier and tier
        identifier, tier = self._get_identifier_and_tier(request)

        # Check rate limit
        limiter = get_rate_limiter()
        result = await limiter.check_rate_limit(
            identifier=identifier,
            tier=tier,
            endpoint=request.url.path,
        )

        # If rate limited, return 429
        if not result.allowed:
            logger.warning(
                "Rate limit exceeded: path=%s, identifier=%s, tier=%s",
                request.url.path, identifier, tier,
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please slow down.",
                        "retry_after": result.retry_after,
                    }
                },
                headers=self._build_rate_limit_headers(result),
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful response
        for header, value in self._build_rate_limit_headers(result).items():
            response.headers[header] = value

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        # Exact match
        if path in self.EXEMPT_PATHS:
            return True

        # Prefix match
        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    def _get_identifier_and_tier(
        self,
        request: Request,
    ) -> Tuple[str, RateLimitTier]:
        """
        Extract identifier and tier from request.

        Uses user_id for authenticated requests, IP for anonymous.
        """
        # Try to get user from request state (set by auth middleware)
        user = getattr(request.state, "user", None)

        if user and hasattr(user, "id"):
            identifier = f"user:{user.id}"

            # Get subscription level
            subscription = getattr(user, "subscription_level", "free")
            tier = subscription_to_tier(subscription)
        else:
            # Unauthenticated - use IP
            client_ip = self._get_client_ip(request)
            identifier = f"ip:{client_ip}"
            tier = RateLimitTier.UNAUTHENTICATED

        return identifier, tier

    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP, considering proxy headers.

        Note: X-Forwarded-For and X-Real-IP headers can be spoofed by
        clients. In production, configure your reverse proxy (nginx/ALB)
        to overwrite these headers so only trusted values are passed.
        """
        # Check X-Forwarded-For first (for proxied requests)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _build_rate_limit_headers(
        self,
        result,
    ) -> Dict[str, str]:
        """Build X-RateLimit-* headers."""
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(int(result.reset_at.timestamp())),
        }

        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)

        return headers
