"""
Authentication and authorization module.

Re-exports key symbols so callers can use:
    from ..core.auth import get_current_user
"""

from .auth import (
    AuthenticationError,
    AuthorizationError,
    CurrentUser,
    get_current_user,
    get_current_user_full,
    get_current_family,
    require_auth,
    decode_token,
    _DEFAULT_USER_ID,
    _DEFAULT_FAMILY_ID,
)
from .auth_helpers import verify_member_belongs_to_family
from .auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    authenticate_user,
    register_user,
)
from .encryption_service import EncryptionService, encryption_service
from .permission_service import UnifiedPermissionService, permission_service

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "CurrentUser",
    "get_current_user",
    "get_current_user_full",
    "get_current_family",
    "require_auth",
    "decode_token",
    "_DEFAULT_USER_ID",
    "_DEFAULT_FAMILY_ID",
    "verify_member_belongs_to_family",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "authenticate_user",
    "register_user",
    "EncryptionService",
    "encryption_service",
    "UnifiedPermissionService",
    "permission_service",
]
