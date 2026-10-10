"""
Unit tests for Devices API endpoint handlers.

Tests the FastAPI route handlers with mocked dependencies.
Integration tests against real DB are skipped due to test infrastructure
FK constraints (medical_resources -> families).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from src.api.v1.devices import (
    RegisterDeviceRequest,
    DeviceTokenResponse,
    register_device_token,
    unregister_device_token,
)


TEST_USER_ID = UUID("123e4567-e89b-12d3-a456-426614174001")

# Patch target: lazy import inside each endpoint function body
_SVC_PATCH = "src.modules.member.device_token_service.DeviceTokenService"


@pytest.mark.unit
@pytest.mark.asyncio
class TestRegisterDeviceToken:
    """Test register_device_token endpoint handler."""

    @patch(_SVC_PATCH)
    async def test_register_success(self, mock_service_cls):
        """Test successful token registration."""
        mock_service = AsyncMock()
        mock_service.register_token.return_value = MagicMock()
        mock_service_cls.return_value = mock_service

        request = RegisterDeviceRequest(
            token="fcm-test-token",
            platform="ios",
            device_name="iPhone 15",
        )

        mock_db = AsyncMock()
        result = await register_device_token(
            request, db=mock_db, user_id=TEST_USER_ID
        )

        assert result.success is True
        assert result.message == "Device token registered"
        mock_service.register_token.assert_awaited_once_with(
            user_id=TEST_USER_ID,
            fcm_token="fcm-test-token",
            device_type="ios",
            device_name="iPhone 15",
        )

    @patch(_SVC_PATCH)
    async def test_register_handles_db_error(self, mock_service_cls):
        """Test that DB errors result in 500."""
        from fastapi import HTTPException

        mock_service = AsyncMock()
        mock_service.register_token.side_effect = RuntimeError("DB error")
        mock_service_cls.return_value = mock_service

        request = RegisterDeviceRequest(
            token="fcm-test",
            platform="android",
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_device_token(
                request, db=AsyncMock(), user_id=TEST_USER_ID
            )

        assert exc_info.value.status_code == 500

    def test_register_validates_platform(self):
        """Test that invalid platform is rejected by Pydantic."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterDeviceRequest(
                token="fcm-test",
                platform="windows",
            )

    def test_register_validates_empty_token(self):
        """Test that empty token is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterDeviceRequest(
                token="",
                platform="ios",
            )

    def test_register_validates_token_max_length(self):
        """Test that token over 500 chars is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterDeviceRequest(
                token="x" * 501,
                platform="ios",
            )

    def test_register_accepts_max_length_token(self):
        """Test that exactly 500 char token is accepted."""
        req = RegisterDeviceRequest(
            token="x" * 500,
            platform="ios",
        )
        assert len(req.token) == 500

    def test_register_optional_fields(self):
        """Test that device_name is optional."""
        req = RegisterDeviceRequest(
            token="fcm-minimal",
            platform="android",
        )
        assert req.device_name is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestUnregisterDeviceToken:
    """Test unregister_device_token endpoint handler."""

    @patch(_SVC_PATCH)
    async def test_unregister_success(self, mock_service_cls):
        """Test successful token unregistration."""
        mock_service = AsyncMock()
        mock_service.deactivate_token.return_value = True
        mock_service_cls.return_value = mock_service

        mock_db = AsyncMock()
        result = await unregister_device_token(
            token="fcm-to-remove", db=mock_db, user_id=TEST_USER_ID
        )

        assert result.success is True
        assert result.message == "Device token unregistered"
        mock_service.deactivate_token.assert_awaited_once_with(
            fcm_token="fcm-to-remove",
            user_id=TEST_USER_ID,
        )

    @patch(_SVC_PATCH)
    async def test_unregister_not_found(self, mock_service_cls):
        """Test that 404 is returned when token is not found."""
        from fastapi import HTTPException

        mock_service = AsyncMock()
        mock_service.deactivate_token.return_value = False
        mock_service_cls.return_value = mock_service

        with pytest.raises(HTTPException) as exc_info:
            await unregister_device_token(
                token="fcm-nonexistent", db=AsyncMock(), user_id=TEST_USER_ID
            )

        assert exc_info.value.status_code == 404

    @patch(_SVC_PATCH)
    async def test_unregister_scoped_to_user(self, mock_service_cls):
        """Test that unregister passes user_id for IDOR prevention."""
        mock_service = AsyncMock()
        mock_service.deactivate_token.return_value = True
        mock_service_cls.return_value = mock_service

        mock_db = AsyncMock()
        await unregister_device_token(
            token="fcm-any", db=mock_db, user_id=TEST_USER_ID
        )

        # Verify user_id is passed (IDOR prevention)
        call_kwargs = mock_service.deactivate_token.call_args.kwargs
        assert call_kwargs["user_id"] == TEST_USER_ID
