"""
Authentication utilities for API endpoints.

Provides dependency injection functions for getting current user and family context.
Uses JWT tokens when an Authorization header is provided; falls back to default
dev UUIDs when STRICT_AUTH_ENABLED=false and no header is present.
"""
import logging
from dataclasses import dataclass
from uuid import UUID
from typing import Optional, Tuple

from fastapi import Header, HTTPException, status
from jose import JWTError

from ...config.settings import settings
from .auth_service import decode_token

_auth_logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication required"):
        self.message = message
        super().__init__(self.message)


class AuthorizationError(Exception):
    """Raised when user lacks permission."""
    def __init__(self, message: str = "Permission denied"):
        self.message = message
        super().__init__(self.message)


# Default test user and family IDs (only used in development mode)
_DEFAULT_USER_ID = UUID("123e4567-e89b-12d3-a456-426614174001")
_DEFAULT_FAMILY_ID = UUID("123e4567-e89b-12d3-a456-426614174000")


def _is_strict_auth_enabled() -> bool:
    """Check if strict authentication is enabled (reads from settings)."""
    return settings.strict_auth_enabled


# Log warning at startup if auth is disabled
if not _is_strict_auth_enabled():
    if settings.environment != "development":
        _auth_logger.critical(
            "STRICT_AUTH_ENABLED=false outside development environment (%s). "
            "Dev-mode auth fallback will NOT activate.",
            settings.environment,
        )
    else:
        _auth_logger.warning(
            "SECURITY WARNING: Authentication is DISABLED (STRICT_AUTH_ENABLED=false). "
            "This should ONLY be used in development environments!"
        )


def _decode_bearer(authorization: Optional[str]) -> Optional[dict]:
    """Try to decode a Bearer token. Returns payload dict or None."""
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    return decode_token(token)


def get_current_user(authorization: Optional[str] = Header(None)) -> UUID:
    """
    Get current user ID — FastAPI dependency.

    When a Bearer token is provided (even in dev mode), it is decoded.
    When no token is provided and strict auth is disabled, returns the
    default dev user ID.
    """
    if authorization:
        try:
            payload = _decode_bearer(authorization)
            if payload:
                if payload.get("type") != "access":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token type — access token required",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return UUID(payload["sub"])
        except (JWTError, KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not _is_strict_auth_enabled() and settings.environment == "development":
        return _DEFAULT_USER_ID

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_family(authorization: Optional[str] = Header(None)) -> UUID:
    """
    Get current family ID — FastAPI dependency.

    Same fallback logic as get_current_user.
    """
    if authorization:
        try:
            payload = _decode_bearer(authorization)
            if payload:
                if payload.get("type") != "access":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token type — access token required",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return UUID(payload["family_id"])
        except (JWTError, KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not _is_strict_auth_enabled() and settings.environment == "development":
        return _DEFAULT_FAMILY_ID

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(user_id: UUID = None, family_id: UUID = None) -> Tuple[UUID, UUID]:
    """
    Helper function to get both user and family ID with error handling.

    Use this in API routes for consistent auth checking.

    Returns:
        Tuple of (user_id, family_id)

    Raises:
        HTTPException: 401 if authentication fails
    """
    try:
        uid = user_id if user_id else get_current_user()
        fid = family_id if family_id else get_current_family()
        return uid, fid
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e.message),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e.message),
        )


@dataclass(frozen=True)
class CurrentUser:
    """Current user context with metadata."""
    user_id: UUID
    family_id: UUID
    username: str
    email: Optional[str] = None


def get_current_user_full(
    authorization: Optional[str] = Header(None),
) -> CurrentUser:
    """
    Get full current user context from JWT token.

    Falls back to default dev user when strict auth is disabled.
    """
    if authorization:
        try:
            payload = _decode_bearer(authorization)
            if payload:
                return CurrentUser(
                    user_id=UUID(payload["sub"]),
                    family_id=UUID(payload["family_id"]),
                    username=payload.get("username", ""),
                    email=payload.get("email"),
                )
        except (JWTError, KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not _is_strict_auth_enabled() and settings.environment == "development":
        return CurrentUser(
            user_id=_DEFAULT_USER_ID,
            family_id=_DEFAULT_FAMILY_ID,
            username="test_user",
            email="test@example.com",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
