"""Reminder domain tool executor — 1 tool for setting reminders."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from ....config.logging import get_logger
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


class ReminderToolExecutor(BaseToolExecutor):
    """Handles set_reminder."""

    async def set_reminder(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.date_manager.models import EventReminder

        title = args.get("title")
        reminder_time_str = args.get("remind_at")

        if not title or not reminder_time_str:
            return tool_error(
                ToolErrorType.VALIDATION,
                "缺少必要参数: title 和 remind_at",
                hint="请提供提醒标题和时间",
            )

        reminder_time = self._parse_reminder_time(reminder_time_str)
        if not reminder_time:
            return tool_error(
                ToolErrorType.VALIDATION,
                f"无效的时间格式: {reminder_time_str}",
            )

        reminder = EventReminder(
            user_id=user_id,
            reminder_type=args.get("reminder_type", "action"),
            content=title,
            trigger_time=reminder_time,
            status="pending",
        )
        self.db.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)

        return {
            "reminder_id": str(reminder.id),
            "title": title,
            "reminder_time": reminder_time.isoformat(),
            "message": f"已设置提醒: {title}",
        }

    @staticmethod
    def _parse_reminder_time(time_str: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            return None
