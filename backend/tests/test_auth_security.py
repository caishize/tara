"""
Tests for JWT authentication hardening across API endpoints.

Validates that:
1. All API endpoints require authentication (401 without token)
2. Valid JWT tokens grant access
3. Invalid/expired tokens are rejected
4. get_current_user and get_current_family behave correctly
"""
import pytest
from unittest.mock import patch
from uuid import UUID, uuid4

from src.core.auth import (
    get_current_user,
    get_current_family,
    _DEFAULT_USER_ID,
    _DEFAULT_FAMILY_ID,
    AuthenticationError,
)
from src.core.auth.auth_service import (
    create_access_token,
    create_refresh_token,
)


# ============ get_current_user Tests ============


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    def test_no_token_strict_mode_raises_401(self):
        """Without a token and strict auth, should raise 401."""
        with patch("src.core.auth.auth.settings") as mock_settings:
            mock_settings.strict_auth_enabled = True
            mock_settings.environment = "production"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(authorization=None)
            assert exc_info.value.status_code == 401

    def test_no_token_dev_mode_returns_default(self):
        """Without a token in dev mode with strict_auth disabled, return default."""
        with patch("src.core.auth.auth.settings") as mock_settings:
            mock_settings.strict_auth_enabled = False
            mock_settings.environment = "development"
            result = get_current_user(authorization=None)
            assert result == _DEFAULT_USER_ID

    def test_valid_access_token(self):
        """A valid access token should return the user_id from the payload."""
        user_id = uuid4()
        family_id = uuid4()
        token = create_access_token(user_id, family_id)
        result = get_current_user(authorization=f"Bearer {token}")
        assert result == user_id

    def test_refresh_token_rejected(self):
        """A refresh token should be rejected (type != access)."""
        user_id = uuid4()
        family_id = uuid4()
        token = create_refresh_token(user_id, family_id)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 401
        assert "Invalid token type" in exc_info.value.detail

    def test_invalid_token_raises_401(self):
        """An invalid/corrupted token should raise 401."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="Bearer invalid.token.here")
        assert exc_info.value.status_code == 401

    def test_no_bearer_prefix_strict_mode(self):
        """A token without Bearer prefix is treated as no token."""
        with patch("src.core.auth.auth.settings") as mock_settings:
            mock_settings.strict_auth_enabled = True
            mock_settings.environment = "production"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(authorization="just-a-token")
            assert exc_info.value.status_code == 401


# ============ get_current_family Tests ============


class TestGetCurrentFamily:
    """Tests for the get_current_family dependency."""

    def test_no_token_strict_mode_raises_401(self):
        """Without a token and strict auth, should raise 401."""
        with patch("src.core.auth.auth.settings") as mock_settings:
            mock_settings.strict_auth_enabled = True
            mock_settings.environment = "production"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                get_current_family(authorization=None)
            assert exc_info.value.status_code == 401

    def test_no_token_dev_mode_returns_default(self):
        """Without a token in dev mode with strict_auth disabled, return default."""
        with patch("src.core.auth.auth.settings") as mock_settings:
            mock_settings.strict_auth_enabled = False
            mock_settings.environment = "development"
            result = get_current_family(authorization=None)
            assert result == _DEFAULT_FAMILY_ID

    def test_valid_access_token(self):
        """A valid access token should return the family_id from the payload."""
        user_id = uuid4()
        family_id = uuid4()
        token = create_access_token(user_id, family_id)
        result = get_current_family(authorization=f"Bearer {token}")
        assert result == family_id

    def test_refresh_token_rejected(self):
        """A refresh token should be rejected (type != access)."""
        user_id = uuid4()
        family_id = uuid4()
        token = create_refresh_token(user_id, family_id)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_family(authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 401


# ============ Hardcoded User ID Elimination Tests ============


class TestNoHardcodedUserIds:
    """Verify that no API route files contain hardcoded user/family UUIDs."""

    # Known mock UUIDs that should NOT appear in route files
    BANNED_UUIDS = [
        "123e4567-e89b-12d3-a456-426614174001",  # Old mock user
        "123e4567-e89b-12d3-a456-426614174000",  # Old mock family
        "87654321-4321-8765-4321-876543218765",  # Old mock user_id
        "12345678-1234-5678-1234-567812345678",  # Old mock family_id
        "00000000-0000-0000-0000-000000000001",  # Old mock research user
    ]

    # Files that should NOT have local get_current_user definitions
    API_ROUTE_FILES = [
        "src/api/v1/auth.py",
        "src/api/v1/chat.py",
        "src/api/v1/dates.py",
        "src/api/v1/members.py",
        "src/api/v1/gifts.py",
        "src/api/v1/gift_browse.py",
        "src/api/v1/gift_memory.py",
        "src/api/v1/kanban.py",
        "src/api/v1/briefing.py",
        "src/api/v1/memory.py",
        "src/api/v1/graph.py",
        "src/api/v1/trips.py",
        "src/api/v1/relationships.py",
        "src/api/v1/actions.py",
        "src/api/v1/curation.py",
        "src/api/v1/devices.py",
        "src/api/v1/people.py",
    ]

    @pytest.mark.parametrize("filepath", API_ROUTE_FILES)
    def test_no_hardcoded_uuids_in_routes(self, filepath):
        """No route file should contain hardcoded mock UUIDs."""
        with open(filepath) as f:
            content = f.read()

        for banned_uuid in self.BANNED_UUIDS:
            assert banned_uuid not in content, (
                f"Found banned UUID {banned_uuid} in {filepath}. "
                "Route files must use Depends(get_current_user) from core.auth."
            )

    @pytest.mark.parametrize("filepath", API_ROUTE_FILES)
    def test_no_local_get_current_user_definition(self, filepath):
        """No route file should define its own get_current_user function."""
        import ast
        with open(filepath) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ("get_current_user", "get_current_user_id"):
                    pytest.fail(
                        f"Found local {node.name}() definition in {filepath} at line {node.lineno}. "
                        "Use `from ...core.auth import get_current_user` instead."
                    )

    @pytest.mark.parametrize("filepath", API_ROUTE_FILES)
    def test_imports_from_core_auth(self, filepath):
        """Each route file should import get_current_user from core.auth."""
        with open(filepath) as f:
            content = f.read()

        assert "core.auth" in content, (
            f"{filepath} does not import from core.auth. "
            "All route files must use centralized auth."
        )
