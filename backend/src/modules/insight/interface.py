"""Insight module public interface.

Defines data contracts for the unified insight system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import ActionType


@dataclass(frozen=True)
class ActionSpec:
    """Typed action spec for insight action chips.

    Serialized as JSON in Insight.action_options column.

    Example::

        ActionSpec(
            label="发送问候",
            action_type=ActionType.OPEN_CHAT,
            action_payload={"recipient_id": "...", "suggested_opener": "..."},
        )
    """
    label: str
    action_type: ActionType
    action_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "label": self.label,
            "action_type": self.action_type.value,
            "action_payload": self.action_payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionSpec":
        """Deserialize from dict (e.g. from JSON column)."""
        action_type_raw = data.get("action_type", ActionType.OPEN_DETAIL.value)
        try:
            action_type = ActionType(action_type_raw)
        except ValueError:
            action_type = ActionType.OPEN_DETAIL
        return cls(
            label=data.get("label", ""),
            action_type=action_type,
            action_payload=data.get("action_payload", {}),
        )


@dataclass(frozen=True)
class InsightEntry:
    """An AI-generated insight."""
    id: str
    insight_type: str
    title: str
    content: str
    priority: int = 5
    urgency: str = "normal"
    status: str = "pending"
    created_at: Optional[datetime] = None
