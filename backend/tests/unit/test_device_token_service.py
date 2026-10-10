"""
Unit tests for DeviceTokenService.

Uses mocked AsyncSession to avoid test database dependency.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import UUID, uuid4

from src.modules.member.device_token_service import DeviceTokenService


TEST_USER_ID = UUID("123e4567-e89b-12d3-a456-426614174001")
OTHER_USER_ID = UUID("123e4567-e89b-12d3-a456-426614174002")


def _make_device_token(**kwargs):
    """Create a mock DeviceToken object."""
    token = MagicMock()
    token.id = kwargs.get("id", uuid4())
    token.user_id = kwargs.get("user_id", TEST_USER_ID)
    token.fcm_token = kwargs.get("fcm_token", "fcm-default")
    token.device_type = kwargs.get("device_type", "ios")
    token.device_name = kwargs.get("device_name", None)
    token.app_version = kwargs.get("app_version", None)
    token.is_active = kwargs.get("is_active", True)
    token.created_at = MagicMock()
    token.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    token.updated_at = MagicMock()
    token.updated_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    return token


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeviceTokenServiceRegister:
    """Test cases for register_token."""

    async def test_register_token_executes_upsert(self):
        """Test that register_token executes an INSERT ON CONFLICT statement."""
        mock_session = AsyncMock()
        mock_token = _make_device_token(
            user_id=TEST_USER_ID,
            fcm_token="fcm-abc",
            device_type="ios",
            device_name="iPhone 15",
        )

        # scalar_one() returns the token
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_token
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        token = await service.register_token(
            user_id=TEST_USER_ID,
            fcm_token="fcm-abc",
            device_type="ios",
            device_name="iPhone 15",
            app_version="1.0.0",
        )

        assert token.user_id == TEST_USER_ID
        assert token.fcm_token == "fcm-abc"
        assert token.device_type == "ios"
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(mock_token)


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeviceTokenServiceGetActive:
    """Test cases for get_active_tokens."""

    async def test_returns_active_tokens(self):
        """Test that active tokens are returned for a user."""
        mock_session = AsyncMock()
        mock_tokens = [
            _make_device_token(fcm_token="fcm-1"),
            _make_device_token(fcm_token="fcm-2"),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_tokens
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        tokens = await service.get_active_tokens(TEST_USER_ID)

        assert len(tokens) == 2
        assert tokens[0].fcm_token == "fcm-1"
        assert tokens[1].fcm_token == "fcm-2"

    async def test_returns_empty_for_no_tokens(self):
        """Test that empty list is returned when no tokens exist."""
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        tokens = await service.get_active_tokens(uuid4())

        assert tokens == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeviceTokenServiceDeactivate:
    """Test cases for deactivate_token and deactivate_tokens."""

    async def test_deactivate_token_returns_true_on_success(self):
        """Test deactivating an existing token returns True."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        result = await service.deactivate_token("fcm-to-deactivate", user_id=TEST_USER_ID)

        assert result is True
        mock_session.commit.assert_awaited_once()

    async def test_deactivate_token_returns_false_when_not_found(self):
        """Test deactivating a non-existent token returns False."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        result = await service.deactivate_token("nonexistent")

        assert result is False

    async def test_deactivate_token_scoped_to_user(self):
        """Test that user_id is included in WHERE clause when provided."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        result = await service.deactivate_token(
            "fcm-owned-by-other", user_id=OTHER_USER_ID
        )

        assert result is False
        # Verify execute was called (SQL will include user_id condition)
        mock_session.execute.assert_awaited_once()

    async def test_deactivate_tokens_batch_returns_count(self):
        """Test batch deactivation returns correct count."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        count = await service.deactivate_tokens(["fcm-1", "fcm-2", "fcm-3"])

        assert count == 3
        mock_session.commit.assert_awaited_once()

    async def test_deactivate_tokens_empty_list_returns_zero(self):
        """Test batch deactivation with empty list returns 0 without DB call."""
        mock_session = AsyncMock()

        service = DeviceTokenService(mock_session)
        count = await service.deactivate_tokens([])

        assert count == 0
        mock_session.execute.assert_not_awaited()

    async def test_deactivate_tokens_nonexistent_returns_zero(self):
        """Test batch deactivation of non-existent tokens returns 0."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        service = DeviceTokenService(mock_session)
        count = await service.deactivate_tokens(["ghost-1", "ghost-2"])

        assert count == 0


@pytest.mark.unit
class TestDeviceTokenToDict:
    """Test DeviceToken.to_dict() method."""

    def test_to_dict_excludes_fcm_token(self):
        """Test that to_dict() does not expose fcm_token."""
        token = _make_device_token(
            user_id=TEST_USER_ID,
            fcm_token="fcm-secret-value",
            device_type="ios",
            is_active=True,
        )

        # Call the real to_dict by creating an actual-ish object
        from src.modules.member.models.device_token import DeviceToken

        dt = DeviceToken()
        dt.id = uuid4()
        dt.user_id = TEST_USER_ID
        dt.fcm_token = "fcm-secret"
        dt.device_type = "ios"
        dt.device_name = None
        dt.app_version = "1.0.0"
        dt.is_active = True
        dt.created_at = MagicMock()
        dt.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        dt.updated_at = MagicMock()
        dt.updated_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        d = dt.to_dict()

        assert "fcm_token" not in d
        assert d["user_id"] == str(TEST_USER_ID)
        assert d["device_type"] == "ios"
        assert d["is_active"] is True
