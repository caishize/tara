"""
Agent context management for Claude Agent SDK.

Provides a unified context structure for agent operations,
including family information and session state.
Business data (trips, memories, calendar) is fetched on-demand via tools.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ..core.utils.timezone import DEFAULT_TIMEZONE_NAME, utc_now


@dataclass
class FamilyMemberInfo:
    """Information about a family member for context."""

    id: UUID
    name: str
    nickname: Optional[str] = None
    relation_type: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None


@dataclass(frozen=True)
class AgentContext:
    """
    Unified context for agent operations.

    This context is passed to the Claude Agent SDK and contains
    only lightweight, always-needed information. Business data
    (trips, memories, schedules) is retrieved on-demand via tools.
    """

    # Identity
    family_id: UUID
    user_id: UUID
    session_id: str

    # Time context
    timezone: str = DEFAULT_TIMEZONE_NAME
    current_time: datetime = field(default_factory=utc_now)

    # Family context (summary only)
    family_members: List[FamilyMemberInfo] = field(default_factory=list)
    member_context_text: str = ""  # One-line summary for system prompt

    # Data summary (counts for agent awareness)
    data_summary: Dict[str, int] = field(default_factory=dict)

    # Data connections
    connected_services: List[str] = field(default_factory=list)

    # Location context
    user_location: Optional[str] = None
    user_coordinates: Optional[Dict[str, float]] = None

    # Conversation history (for context, not stored here)
    conversation_summary: str = ""

    def to_system_prompt_context(self) -> str:
        """
        Generate context text for inclusion in system prompt.

        Returns a formatted string containing only lightweight context.
        Business data is excluded — the agent retrieves it via tools.
        """
        sections = []

        # Current time
        sections.append(f"【当前时间】\n{self.current_time.strftime('%Y-%m-%d %H:%M')} ({self.timezone})")

        # User location
        if self.user_location:
            sections.append(f"【用户位置】\n{self.user_location}")

        # Family members (summary only)
        if self.member_context_text:
            sections.append(f"【家庭成员】\n{self.member_context_text}")
        elif self.family_members:
            members_text = self._format_members()
            sections.append(f"【家庭成员】\n{members_text}")

        # Connected services
        if self.connected_services:
            services = ", ".join(self.connected_services)
            sections.append(f"【已连接服务】\n{services}")

        # Data summary (counts to guide agent tool usage)
        if self.data_summary:
            summary_parts = []
            if self.data_summary.get("trips", 0) > 0:
                summary_parts.append(f"{self.data_summary['trips']} 个进行中的旅行计划")
            if self.data_summary.get("tasks", 0) > 0:
                summary_parts.append(f"{self.data_summary['tasks']} 条待办事项")
            if self.data_summary.get("pending_actions", 0) > 0:
                summary_parts.append(f"{self.data_summary['pending_actions']} 个待确认操作")
            if summary_parts:
                sections.append(f"【数据概况】当前有{'、'.join(summary_parts)}。如需详情请使用对应工具查询。")

        if self.conversation_summary:
            sections.append(f"【对话历史】\n{self.conversation_summary}")

        return "\n\n".join(sections)

    def _format_members(self) -> str:
        """Format family members as a one-line summary."""
        if not self.family_members:
            return "暂无家庭成员信息"

        parts = []
        for m in self.family_members:
            info = m.nickname or m.name
            detail_parts = []
            if m.relation_type:
                info = f"{m.relation_type}·{info}"
            if m.gender:
                detail_parts.append("男" if m.gender == "male" else "女")
            if m.age:
                detail_parts.append(f"{m.age}岁")
            if detail_parts:
                info += f"({','.join(detail_parts)})"
            parts.append(info)

        return "家庭成员：" + "、".join(parts)


class ContextBuilder:
    """
    Builder for constructing AgentContext using immutable patterns.

    Provides a fluent interface for building context with
    optional components. Each method returns a new builder instance
    to maintain immutability.
    """

    def __init__(
        self,
        family_id: UUID,
        user_id: UUID,
        session_id: str,
        _context: Optional[AgentContext] = None,
    ):
        if _context is not None:
            self._context = _context
        else:
            self._context = AgentContext(
                family_id=family_id,
                user_id=user_id,
                session_id=session_id,
            )

    def _with_updated_context(self, **kwargs: Any) -> "ContextBuilder":
        """Create a new builder with updated context (immutable pattern)."""
        new_context = replace(self._context, **kwargs)
        return ContextBuilder(
            family_id=self._context.family_id,
            user_id=self._context.user_id,
            session_id=self._context.session_id,
            _context=new_context,
        )

    def with_timezone(self, timezone: str) -> "ContextBuilder":
        """Set the timezone."""
        return self._with_updated_context(timezone=timezone)

    def with_current_time(self, current_time: datetime) -> "ContextBuilder":
        """Set the current time."""
        return self._with_updated_context(current_time=current_time)

    def with_family_members(
        self,
        members: List[FamilyMemberInfo],
        context_text: Optional[str] = None,
    ) -> "ContextBuilder":
        """Add family members."""
        updates: Dict[str, Any] = {"family_members": members}
        if context_text:
            updates["member_context_text"] = context_text
        return self._with_updated_context(**updates)

    def with_data_summary(self, summary: Dict[str, int]) -> "ContextBuilder":
        """Add data summary counts."""
        return self._with_updated_context(data_summary=summary)

    def with_connected_services(self, services: List[str]) -> "ContextBuilder":
        """Add connected services."""
        return self._with_updated_context(connected_services=services)

    def with_location(
        self,
        location: Optional[str] = None,
        coordinates: Optional[Dict[str, float]] = None,
    ) -> "ContextBuilder":
        """Set the user location."""
        updates: Dict[str, Any] = {}
        if location is not None:
            updates["user_location"] = location
        if coordinates is not None:
            updates["user_coordinates"] = coordinates
        return self._with_updated_context(**updates) if updates else self

    def with_conversation_summary(self, summary: str) -> "ContextBuilder":
        """Add conversation summary."""
        return self._with_updated_context(conversation_summary=summary)

    def build(self) -> AgentContext:
        """Build the final context."""
        return self._context
