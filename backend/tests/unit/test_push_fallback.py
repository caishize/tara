"""
Unit tests for push notification fallback in RedisPubSubManager.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from src.core.pubsub.redis_pubsub import RedisPubSubManager


TEST_USER_ID = "123e4567-e89b-12d3-a456-426614174001"
TEST_ACTION_ID = "action-abc-123"
DISPLAY_DATA = {
    "title": "确认购买",
    "details": [
        {"label": "商品", "value": "Apple AirPods Pro"},
        {"label": "价格", "value": "¥1,799"},
    ],
}


@pytest.mark.unit
@pytest.mark.asyncio
class TestPublishConfirmCard:
    """Test publish_confirm_card with push fallback."""

    @pytest.fixture
    def manager(self):
        """Create a RedisPubSubManager with mocked Redis."""
        m = RedisPubSubManager()
        m._publisher = AsyncMock()
        return m

    async def test_publish_with_subscribers_no_fallback(self, manager):
        """When WebSocket has subscribers, no push fallback should fire."""
        manager._publisher.publish = AsyncMock(return_value=1)

        with patch.object(manager, "_send_push_fallback") as mock_push:
            receivers = await manager.publish_confirm_card(
                user_id=TEST_USER_ID,
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
                trace_id="trace-001",
            )

        assert receivers == 1
        mock_push.assert_not_called()

    async def test_publish_no_subscribers_triggers_fallback(self, manager):
        """When 0 subscribers, push fallback should be called."""
        manager._publisher.publish = AsyncMock(return_value=0)

        with patch.object(
            manager, "_send_push_fallback", new_callable=AsyncMock
        ) as mock_push:
            receivers = await manager.publish_confirm_card(
                user_id=TEST_USER_ID,
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
                trace_id="trace-002",
            )

        assert receivers == 0
        mock_push.assert_awaited_once_with(
            user_id=TEST_USER_ID,
            action_id=TEST_ACTION_ID,
            action_type="purchase",
            display_data=DISPLAY_DATA,
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestSendPushFallback:
    """Test _send_push_fallback logic."""

    @patch("src.core.pubsub.redis_pubsub.settings")
    async def test_skips_when_fcm_disabled(self, mock_settings):
        """Test that fallback is a no-op when FCM is disabled."""
        mock_settings.fcm_enabled = False
        manager = RedisPubSubManager()

        await manager._send_push_fallback(
            user_id=TEST_USER_ID,
            action_id=TEST_ACTION_ID,
            action_type="purchase",
            display_data=DISPLAY_DATA,
        )

    @patch("src.core.pubsub.redis_pubsub.settings")
    async def test_handles_exception_gracefully(self, mock_settings):
        """Test that exceptions in push fallback don't propagate."""
        mock_settings.fcm_enabled = True
        manager = RedisPubSubManager()

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("DB unavailable"))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker = MagicMock(return_value=mock_session_cm)

        with patch("src.db.session.async_session_maker", mock_session_maker):
            # Should not raise
            await manager._send_push_fallback(
                user_id=TEST_USER_ID,
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
            )


@pytest.mark.unit
@pytest.mark.asyncio
class TestDoPushSend:
    """Test _do_push_send static method."""

    async def test_skips_when_no_device_tokens(self):
        """Test that push is skipped when user has no registered devices."""
        mock_session = AsyncMock()
        mock_token_service = AsyncMock()
        mock_token_service.get_active_tokens.return_value = []

        mock_send = AsyncMock(return_value=[])

        with patch(
            "src.modules.member.device_token_service.DeviceTokenService",
            return_value=mock_token_service,
        ), patch(
            "src.core.push.fcm_service.send_to_user",
            mock_send,
        ):
            await RedisPubSubManager._do_push_send(
                session=mock_session,
                user_id=UUID(TEST_USER_ID),
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
            )

        mock_send.assert_not_called()

    async def test_sends_push_and_deactivates_invalid_tokens(self):
        """Test that push is sent and invalid tokens are cleaned up."""
        mock_session = AsyncMock()

        mock_dt1 = MagicMock()
        mock_dt1.fcm_token = "fcm-valid"
        mock_dt2 = MagicMock()
        mock_dt2.fcm_token = "fcm-invalid"

        mock_token_service = AsyncMock()
        mock_token_service.get_active_tokens.return_value = [mock_dt1, mock_dt2]

        mock_send = AsyncMock(return_value=["fcm-invalid"])

        with patch(
            "src.modules.member.device_token_service.DeviceTokenService",
            return_value=mock_token_service,
        ), patch(
            "src.core.push.fcm_service.send_to_user",
            mock_send,
        ):
            await RedisPubSubManager._do_push_send(
                session=mock_session,
                user_id=UUID(TEST_USER_ID),
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
            )

        mock_send.assert_awaited_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs["tokens"] == ["fcm-valid", "fcm-invalid"]
        assert call_kwargs.kwargs["data"]["type"] == "pending_action"
        assert call_kwargs.kwargs["data"]["action_id"] == TEST_ACTION_ID

        mock_token_service.deactivate_tokens.assert_awaited_once_with(["fcm-invalid"])

    async def test_formats_body_from_display_details(self):
        """Test that notification body is built from display_data details."""
        mock_session = AsyncMock()
        mock_dt = MagicMock()
        mock_dt.fcm_token = "fcm-tok"

        mock_token_service = AsyncMock()
        mock_token_service.get_active_tokens.return_value = [mock_dt]

        mock_send = AsyncMock(return_value=[])

        with patch(
            "src.modules.member.device_token_service.DeviceTokenService",
            return_value=mock_token_service,
        ), patch(
            "src.core.push.fcm_service.send_to_user",
            mock_send,
        ):
            await RedisPubSubManager._do_push_send(
                session=mock_session,
                user_id=UUID(TEST_USER_ID),
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
            )

        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["title"] == "确认购买"
        assert "Apple AirPods Pro" in call_kwargs["body"]
        assert "¥1,799" in call_kwargs["body"]

    async def test_no_deactivation_when_all_tokens_valid(self):
        """Test that deactivate_tokens is not called when no invalid tokens."""
        mock_session = AsyncMock()
        mock_dt = MagicMock()
        mock_dt.fcm_token = "fcm-all-good"

        mock_token_service = AsyncMock()
        mock_token_service.get_active_tokens.return_value = [mock_dt]

        mock_send = AsyncMock(return_value=[])

        with patch(
            "src.modules.member.device_token_service.DeviceTokenService",
            return_value=mock_token_service,
        ), patch(
            "src.core.push.fcm_service.send_to_user",
            mock_send,
        ):
            await RedisPubSubManager._do_push_send(
                session=mock_session,
                user_id=UUID(TEST_USER_ID),
                action_id=TEST_ACTION_ID,
                action_type="purchase",
                display_data=DISPLAY_DATA,
            )

        mock_token_service.deactivate_tokens.assert_not_called()
