"""Tests for push budget enforcement in AppNotificationProvider.

V8-Brain S7.2: Max 5 proactive pushes/day/user, P0 (URGENT) exempted.
"""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.core.push.notification_provider import (
    AppNotificationProvider,
    _PRIORITY_TO_LEVEL,
)
from src.core.interfaces.notification_provider import (
    NotificationChannel,
    NotificationPriority,
)


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------


class TestPriorityMapping:

    def test_urgent_maps_to_p0(self):
        assert _PRIORITY_TO_LEVEL["urgent"] == "P0"

    def test_high_maps_to_p1(self):
        assert _PRIORITY_TO_LEVEL["high"] == "P1"

    def test_normal_maps_to_p2(self):
        assert _PRIORITY_TO_LEVEL["normal"] == "P2"

    def test_low_maps_to_p3(self):
        assert _PRIORITY_TO_LEVEL["low"] == "P3"


# ---------------------------------------------------------------------------
# Budget enforcement in send_notification
# ---------------------------------------------------------------------------


class TestPushBudgetEnforcement:

    @pytest.fixture()
    def provider(self):
        return AppNotificationProvider()

    @pytest.mark.asyncio
    async def test_budget_exhausted_suppresses_push(self, provider):
        """When can_push returns False, notification is suppressed."""
        user_id = str(uuid4())
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
            return_value=False,
        ) as mock_can:
            result = await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient=user_id,
                title="Test",
                content="Body",
                priority=NotificationPriority.NORMAL,
            )

        assert result["success"] is False
        assert result["error"] == "daily_push_budget_exhausted"
        mock_can.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_budget_available_allows_push(self, provider):
        """When can_push returns True, notification is sent and recorded."""
        user_id = str(uuid4())
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "src.core.push.notification_provider.record_push",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_record:
            result = await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient=user_id,
                title="Test",
                content="Body",
                priority=NotificationPriority.NORMAL,
            )

        assert result["success"] is True
        mock_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_urgent_bypasses_budget(self, provider):
        """P0/URGENT always sends, even when budget check would fail."""
        user_id = str(uuid4())
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "src.core.push.notification_provider.record_push",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_record:
            result = await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient=user_id,
                title="URGENT",
                content="Urgent body",
                priority=NotificationPriority.URGENT,
            )

        assert result["success"] is True
        # P0 should NOT call record_push (they bypass the budget)
        mock_record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_p0_can_push_called_with_correct_priority(self, provider):
        """can_push receives 'P0' for URGENT, which always returns True."""
        user_id = str(uuid4())
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_can, patch(
            "src.core.push.notification_provider.record_push",
            new_callable=AsyncMock,
        ):
            await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient=user_id,
                title="Test",
                content="Body",
                priority=NotificationPriority.URGENT,
            )

        from uuid import UUID
        call_args = mock_can.call_args
        assert call_args[0][0] == UUID(user_id)
        assert call_args[1]["priority_level"] == "P0"

    @pytest.mark.asyncio
    async def test_non_uuid_recipient_skips_budget_check(self, provider):
        """If recipient is not a valid UUID, budget check is skipped."""
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
        ) as mock_can, patch(
            "src.core.push.notification_provider.record_push",
            new_callable=AsyncMock,
        ):
            result = await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient="not-a-uuid",
                title="Test",
                content="Body",
                priority=NotificationPriority.NORMAL,
            )

        assert result["success"] is True
        mock_can.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_high_priority_uses_p1(self, provider):
        """HIGH priority maps to P1."""
        user_id = str(uuid4())
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_can, patch(
            "src.core.push.notification_provider.record_push",
            new_callable=AsyncMock,
        ):
            await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient=user_id,
                title="Test",
                content="Body",
                priority=NotificationPriority.HIGH,
            )

        from uuid import UUID
        assert mock_can.call_args[1]["priority_level"] == "P1"

    @pytest.mark.asyncio
    async def test_low_priority_uses_p3(self, provider):
        """LOW priority maps to P3."""
        user_id = str(uuid4())
        with patch(
            "src.core.push.notification_provider.can_push",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_can, patch(
            "src.core.push.notification_provider.record_push",
            new_callable=AsyncMock,
        ):
            await provider.send_notification(
                channel=NotificationChannel.APP,
                recipient=user_id,
                title="Test",
                content="Body",
                priority=NotificationPriority.LOW,
            )

        assert mock_can.call_args[1]["priority_level"] == "P3"
