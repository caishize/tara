"""
Unit tests for FCM push notification service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetFirebaseApp:
    """Test cases for _get_firebase_app lazy initialization."""

    def setup_method(self):
        """Reset global state before each test."""
        import src.core.push.fcm_service as mod
        mod._firebase_app = None

    @patch("src.core.push.fcm_service.settings")
    def test_returns_none_when_fcm_disabled(self, mock_settings):
        """Test that None is returned when FCM is disabled."""
        from src.core.push.fcm_service import _get_firebase_app

        mock_settings.fcm_enabled = False
        assert _get_firebase_app() is None

    @patch("src.core.push.fcm_service.settings")
    def test_returns_none_when_path_not_set(self, mock_settings):
        """Test that None is returned when service account path is missing."""
        from src.core.push.fcm_service import _get_firebase_app

        mock_settings.fcm_enabled = True
        mock_settings.firebase_service_account_path = None
        assert _get_firebase_app() is None

    @patch("src.core.push.fcm_service.settings")
    def test_returns_none_when_file_not_found(self, mock_settings, tmp_path):
        """Test that None is returned when the file doesn't exist."""
        from src.core.push.fcm_service import _get_firebase_app

        mock_settings.fcm_enabled = True
        mock_settings.firebase_service_account_path = str(tmp_path / "nonexistent.json")
        assert _get_firebase_app() is None

    @patch("src.core.push.fcm_service.settings")
    def test_returns_none_when_file_not_json(self, mock_settings, tmp_path):
        """Test that non-.json files are rejected."""
        from src.core.push.fcm_service import _get_firebase_app

        bad_file = tmp_path / "creds.txt"
        bad_file.write_text("{}")

        mock_settings.fcm_enabled = True
        mock_settings.firebase_service_account_path = str(bad_file)
        assert _get_firebase_app() is None

    def test_caches_firebase_app(self):
        """Test that _firebase_app is cached after first init."""
        import src.core.push.fcm_service as mod

        sentinel = MagicMock()
        mod._firebase_app = sentinel

        result = mod._get_firebase_app()
        assert result is sentinel


@pytest.mark.unit
@pytest.mark.asyncio
class TestSendToUser:
    """Test cases for send_to_user function."""

    def setup_method(self):
        import src.core.push.fcm_service as mod
        mod._firebase_app = None

    @patch("src.core.push.fcm_service._get_firebase_app", return_value=None)
    async def test_returns_empty_when_no_app(self, mock_app):
        """Test returns empty list when Firebase is not initialized."""
        from src.core.push.fcm_service import send_to_user

        result = await send_to_user(
            tokens=["token1"],
            title="Test",
            body="Hello",
        )
        assert result == []

    @patch("src.core.push.fcm_service._get_firebase_app")
    async def test_returns_empty_when_no_tokens(self, mock_app):
        """Test returns empty list when tokens list is empty."""
        from src.core.push.fcm_service import send_to_user

        mock_app.return_value = MagicMock()
        result = await send_to_user(tokens=[], title="Test", body="Hello")
        assert result == []

    def _make_firebase_modules(self, mock_messaging):
        """Build patched sys.modules dict for firebase_admin with linked messaging."""
        mock_firebase_admin = MagicMock()
        mock_firebase_admin.messaging = mock_messaging
        return {
            "firebase_admin": mock_firebase_admin,
            "firebase_admin.messaging": mock_messaging,
        }

    async def test_sends_multicast_and_returns_invalid_tokens(self):
        """Test successful multicast send with some invalid tokens."""
        import src.core.push.fcm_service as mod

        mod._firebase_app = MagicMock()

        mock_messaging = MagicMock()

        ok_response = MagicMock()
        ok_response.exception = None

        invalid_response = MagicMock()
        invalid_response.exception = MagicMock()
        invalid_response.exception.code = "NOT_FOUND"

        unregistered_response = MagicMock()
        unregistered_response.exception = MagicMock()
        unregistered_response.exception.code = "UNREGISTERED"

        mock_batch_response = MagicMock()
        mock_batch_response.responses = [ok_response, invalid_response, unregistered_response]
        mock_batch_response.success_count = 1
        mock_batch_response.failure_count = 2

        mock_messaging.send_each_for_multicast.return_value = mock_batch_response

        with patch.dict("sys.modules", self._make_firebase_modules(mock_messaging)):
            result = await mod.send_to_user(
                tokens=["token-ok", "token-invalid", "token-unregistered"],
                title="需要您确认",
                body="购买商品: ¥299",
                data={"type": "pending_action", "action_id": "abc-123"},
            )

        assert "token-invalid" in result
        assert "token-unregistered" in result
        assert "token-ok" not in result

    async def test_handles_send_exception_gracefully(self):
        """Test that exceptions during send are caught and return empty list."""
        import src.core.push.fcm_service as mod
        mod._firebase_app = MagicMock()

        mock_messaging = MagicMock()
        mock_messaging.send_each_for_multicast.side_effect = RuntimeError("Network error")

        with patch.dict("sys.modules", self._make_firebase_modules(mock_messaging)):
            result = await mod.send_to_user(
                tokens=["token1"],
                title="Test",
                body="Hello",
            )

        assert result == []

    async def test_retryable_errors_not_flagged_as_invalid(self):
        """Test that non-permanent errors don't mark tokens as invalid."""
        import src.core.push.fcm_service as mod
        mod._firebase_app = MagicMock()

        mock_messaging = MagicMock()

        temp_error_response = MagicMock()
        temp_error_response.exception = MagicMock()
        temp_error_response.exception.code = "QUOTA_EXCEEDED"

        mock_batch_response = MagicMock()
        mock_batch_response.responses = [temp_error_response]
        mock_batch_response.success_count = 0
        mock_batch_response.failure_count = 1

        mock_messaging.send_each_for_multicast.return_value = mock_batch_response

        with patch.dict("sys.modules", self._make_firebase_modules(mock_messaging)):
            result = await mod.send_to_user(
                tokens=["token-temp-error"],
                title="Test",
                body="Hello",
            )

        # QUOTA_EXCEEDED should NOT mark token as invalid
        assert result == []
