"""
Unit tests for the refactored AgentContext and ContextRehydrationService.

Validates that:
- System prompt no longer contains trip/memory/calendar data
- Data summary counts are included in the system prompt
- ContextBuilder no longer has with_trips/with_memories methods
- Member context returns summary format
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.ai_engine.agent_context import (
    AgentContext,
    ContextBuilder,
    FamilyMemberInfo,
)


class TestAgentContext:
    """Tests for the refactored AgentContext dataclass."""

    def _make_context(self, **overrides):
        """Create a test AgentContext with sensible defaults."""
        defaults = {
            "family_id": uuid4(),
            "user_id": uuid4(),
            "session_id": "test-session",
            "timezone": "Asia/Shanghai",
            "current_time": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
        }
        defaults.update(overrides)
        return AgentContext(**defaults)

    def test_system_prompt_excludes_trips(self):
        """System prompt must NOT contain trip data sections."""
        ctx = self._make_context()
        prompt = ctx.to_system_prompt_context()
        assert "进行中的旅行" not in prompt or "数据概况" in prompt
        assert "→" not in prompt  # Trip format used arrows

    def test_system_prompt_excludes_memories(self):
        """System prompt must NOT contain memory data sections."""
        ctx = self._make_context()
        prompt = ctx.to_system_prompt_context()
        assert "相关记忆" not in prompt

    def test_system_prompt_excludes_calendar(self):
        """System prompt must NOT contain calendar data sections."""
        ctx = self._make_context()
        prompt = ctx.to_system_prompt_context()
        assert "近期日程" not in prompt

    def test_system_prompt_includes_time(self):
        """System prompt must include current time."""
        ctx = self._make_context()
        prompt = ctx.to_system_prompt_context()
        assert "当前时间" in prompt
        assert "2026-01-15 10:30" in prompt

    def test_system_prompt_includes_location(self):
        """System prompt must include user location when set."""
        ctx = self._make_context(user_location="北京")
        prompt = ctx.to_system_prompt_context()
        assert "用户位置" in prompt
        assert "北京" in prompt

    def test_system_prompt_includes_data_summary(self):
        """System prompt must include data summary counts."""
        ctx = self._make_context(
            data_summary={"trips": 3, "tasks": 5, "pending_actions": 2}
        )
        prompt = ctx.to_system_prompt_context()
        assert "数据概况" in prompt
        assert "3 个进行中的旅行计划" in prompt
        assert "5 条待办事项" in prompt
        assert "2 个待确认操作" in prompt
        assert "如需详情请使用对应工具查询" in prompt

    def test_system_prompt_data_summary_empty_counts_omitted(self):
        """Data summary with zero counts should not appear."""
        ctx = self._make_context(
            data_summary={"trips": 0, "tasks": 0, "pending_actions": 0}
        )
        prompt = ctx.to_system_prompt_context()
        assert "数据概况" not in prompt

    def test_system_prompt_data_summary_partial_counts(self):
        """Only non-zero counts should appear in data summary."""
        ctx = self._make_context(
            data_summary={"trips": 2, "tasks": 0, "pending_actions": 0}
        )
        prompt = ctx.to_system_prompt_context()
        assert "数据概况" in prompt
        assert "2 个进行中的旅行计划" in prompt
        assert "待办事项" not in prompt
        assert "待确认操作" not in prompt

    def test_system_prompt_includes_member_summary(self):
        """System prompt must include member summary text."""
        ctx = self._make_context(
            member_context_text="家庭成员：老板(男,35岁)、太太·小丽(女,32岁)"
        )
        prompt = ctx.to_system_prompt_context()
        assert "家庭成员" in prompt
        assert "老板" in prompt
        assert "小丽" in prompt

    def test_format_members_summary_format(self):
        """_format_members should produce a one-line summary."""
        members = [
            FamilyMemberInfo(
                id=uuid4(), name="张三", nickname="老板",
                relation_type=None, age=35, gender="male",
            ),
            FamilyMemberInfo(
                id=uuid4(), name="李丽", nickname="小丽",
                relation_type="太太", age=32, gender="female",
            ),
        ]
        ctx = self._make_context(family_members=members)
        result = ctx._format_members()
        assert "家庭成员：" in result
        assert "老板" in result
        assert "太太·小丽" in result
        assert "男" in result
        assert "35岁" in result

    def test_no_trip_fields_on_dataclass(self):
        """AgentContext should not have trip/memory/calendar text fields."""
        ctx = self._make_context()
        assert not hasattr(ctx, "trip_context_text")
        assert not hasattr(ctx, "calendar_context_text")
        assert not hasattr(ctx, "memory_context_text")
        assert not hasattr(ctx, "recalled_memories")
        assert not hasattr(ctx, "active_trips")
        assert not hasattr(ctx, "calendar_events")

    def test_has_data_summary_field(self):
        """AgentContext should have data_summary field."""
        ctx = self._make_context()
        assert hasattr(ctx, "data_summary")
        assert isinstance(ctx.data_summary, dict)


class TestContextBuilder:
    """Tests for the refactored ContextBuilder."""

    def test_builder_no_with_trips(self):
        """ContextBuilder must NOT have with_trips method."""
        builder = ContextBuilder(
            family_id=uuid4(), user_id=uuid4(), session_id="test"
        )
        assert not hasattr(builder, "with_trips")

    def test_builder_no_with_memories(self):
        """ContextBuilder must NOT have with_memories method."""
        builder = ContextBuilder(
            family_id=uuid4(), user_id=uuid4(), session_id="test"
        )
        assert not hasattr(builder, "with_memories")

    def test_builder_no_with_calendar(self):
        """ContextBuilder must NOT have with_calendar method."""
        builder = ContextBuilder(
            family_id=uuid4(), user_id=uuid4(), session_id="test"
        )
        assert not hasattr(builder, "with_calendar")

    def test_builder_has_with_data_summary(self):
        """ContextBuilder must have with_data_summary method."""
        builder = ContextBuilder(
            family_id=uuid4(), user_id=uuid4(), session_id="test"
        )
        assert hasattr(builder, "with_data_summary")

    def test_builder_with_data_summary(self):
        """with_data_summary should set the data_summary field."""
        summary = {"trips": 3, "tasks": 5, "pending_actions": 2}
        ctx = (
            ContextBuilder(family_id=uuid4(), user_id=uuid4(), session_id="test")
            .with_data_summary(summary)
            .build()
        )
        assert ctx.data_summary == summary

    def test_builder_immutability(self):
        """Builder methods should return new instances (immutable)."""
        builder1 = ContextBuilder(
            family_id=uuid4(), user_id=uuid4(), session_id="test"
        )
        builder2 = builder1.with_timezone("America/New_York")
        assert builder1 is not builder2
        assert builder1._context.timezone == "Asia/Shanghai"
        assert builder2._context.timezone == "America/New_York"

    def test_builder_full_chain(self):
        """Full builder chain should produce correct context."""
        family_id = uuid4()
        user_id = uuid4()
        members = [
            FamilyMemberInfo(
                id=uuid4(), name="测试", age=30, gender="male",
            )
        ]
        summary = {"trips": 1, "pending_actions": 0}

        ctx = (
            ContextBuilder(family_id=family_id, user_id=user_id, session_id="s1")
            .with_timezone("Asia/Tokyo")
            .with_current_time(datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc))
            .with_family_members(members, "家庭成员：测试(男,30岁)")
            .with_data_summary(summary)
            .with_connected_services(["calendar", "weather"])
            .with_location(location="东京")
            .build()
        )

        assert ctx.family_id == family_id
        assert ctx.timezone == "Asia/Tokyo"
        assert len(ctx.family_members) == 1
        assert ctx.data_summary == summary
        assert ctx.connected_services == ["calendar", "weather"]
        assert ctx.user_location == "东京"

        prompt = ctx.to_system_prompt_context()
        assert "东京" in prompt
        assert "1 个进行中的旅行计划" in prompt
