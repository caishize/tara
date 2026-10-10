"""Tests for InsightContextAssembler - context assembly for insight generation."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.core.utils.xml_escape import escape_xml
from src.modules.insight.insight_context_assembler import (
    InsightContext,
    InsightContextAssembler,
)


# ---------------------------------------------------------------------------
# InsightContext.to_prompt_xml
# ---------------------------------------------------------------------------


class TestInsightContextXml:
    """Verify XML serialization of InsightContext."""

    def test_empty_context_returns_empty_string(self):
        ctx = InsightContext()
        assert ctx.to_prompt_xml() == ""

    def test_person_profiles_section(self):
        ctx = InsightContext(
            person_profiles=[
                {
                    "name": "张三",
                    "relationship": "大学室友",
                    "location": "北京",
                    "preferences": {"likes": ["咖啡", "跑步"]},
                    "favor_balance": -1.0,
                    "importance": 8,
                    "days_since_contact": 45,
                }
            ]
        )
        xml = ctx.to_prompt_xml()
        assert "<insight_context>" in xml
        assert "<person_profiles>" in xml
        assert "<name>张三</name>" in xml
        assert "<relationship>大学室友</relationship>" in xml
        assert "<location>北京</location>" in xml
        assert "<likes>咖啡, 跑步</likes>" in xml
        assert "<favor_balance>-1.0</favor_balance>" in xml
        assert "<importance>8</importance>" in xml
        assert "<days_since_contact>45</days_since_contact>" in xml

    def test_memory_summaries_section(self):
        ctx = InsightContext(
            memory_summaries=[
                {
                    "summary_type": "weekly",
                    "title": "本周回顾",
                    "content": "这周工作比较忙",
                    "importance": 7,
                }
            ]
        )
        xml = ctx.to_prompt_xml()
        assert "<memory_summaries>" in xml
        assert "<type>weekly</type>" in xml
        assert "<title>本周回顾</title>" in xml
        assert "<content>这周工作比较忙</content>" in xml

    def test_emotional_trend_section(self):
        ctx = InsightContext(
            emotional_trend={
                "trend": "declining",
                "negative_count": 5,
                "positive_count": 1,
                "suggested_tone": "empathetic",
            }
        )
        xml = ctx.to_prompt_xml()
        assert "<emotional_trend>" in xml
        assert "<trend>declining</trend>" in xml
        assert "<negative_count>5</negative_count>" in xml
        assert "<suggested_tone>empathetic</suggested_tone>" in xml

    def test_unknown_emotional_trend_excluded(self):
        ctx = InsightContext(
            emotional_trend={"trend": "unknown"},
            person_profiles=[{"name": "李四"}],
        )
        xml = ctx.to_prompt_xml()
        assert "<emotional_trend>" not in xml
        assert "<person_profiles>" in xml

    def test_preference_rules_section(self):
        ctx = InsightContext(
            preference_rules=[
                {
                    "action": "suppress",
                    "explanation": "用户不喜欢收到天气提醒",
                    "condition_event_type": "weather",
                }
            ]
        )
        xml = ctx.to_prompt_xml()
        assert "<preference_rules>" in xml
        assert "<action>suppress</action>" in xml
        assert "<explanation>用户不喜欢收到天气提醒</explanation>" in xml
        assert "<event_type>weather</event_type>" in xml

    def test_xml_escaping(self):
        ctx = InsightContext(
            person_profiles=[
                {
                    "name": "A & B",
                    "relationship": '<"test">',
                }
            ]
        )
        xml = ctx.to_prompt_xml()
        assert "A &amp; B" in xml
        assert "&lt;&quot;test&quot;&gt;" in xml

    def test_combined_sections(self):
        ctx = InsightContext(
            person_profiles=[{"name": "王五"}],
            memory_summaries=[{"summary_type": "weekly", "title": "t", "content": "c"}],
            emotional_trend={
                "trend": "stable",
                "negative_count": 2,
                "positive_count": 2,
                "suggested_tone": "neutral",
            },
            preference_rules=[{"action": "deprioritize", "explanation": "test"}],
        )
        xml = ctx.to_prompt_xml()
        assert "<insight_context>" in xml
        assert "</insight_context>" in xml
        assert "<person_profiles>" in xml
        assert "<memory_summaries>" in xml
        assert "<emotional_trend>" in xml
        assert "<preference_rules>" in xml


# ---------------------------------------------------------------------------
# _escape helper
# ---------------------------------------------------------------------------


class TestEscapeXml:

    def test_ampersand(self):
        assert escape_xml("A & B") == "A &amp; B"

    def test_lt_gt(self):
        assert escape_xml("<tag>") == "&lt;tag&gt;"

    def test_quote(self):
        assert escape_xml('"hello"') == "&quot;hello&quot;"

    def test_no_special(self):
        assert escape_xml("plain text") == "plain text"


# ---------------------------------------------------------------------------
# InsightContextAssembler.assemble (mocked DB)
# ---------------------------------------------------------------------------


class TestInsightContextAssembler:
    """Test the assembler with mocked DB calls."""

    @pytest.fixture()
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture()
    def assembler(self, mock_db):
        return InsightContextAssembler(mock_db)

    @pytest.fixture()
    def user_id(self):
        return uuid4()

    @pytest.fixture()
    def family_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_assemble_returns_insight_context(
        self, assembler, user_id, family_id,
    ):
        """Assemble returns InsightContext even when DB returns empty."""
        with (
            patch.object(
                assembler, "_fetch_person_profiles", return_value=[],
            ),
            patch.object(
                assembler, "_fetch_memory_summaries", return_value=[],
            ),
            patch.object(
                assembler, "_fetch_emotional_trend", return_value=None,
            ),
            patch.object(
                assembler, "_fetch_preference_rules", return_value=[],
            ),
        ):
            ctx = await assembler.assemble(user_id, family_id)

        assert isinstance(ctx, InsightContext)
        assert ctx.person_profiles == ()
        assert ctx.memory_summaries == ()
        assert ctx.emotional_trend is None
        assert ctx.preference_rules == ()

    @pytest.mark.asyncio
    async def test_assemble_with_profiles(
        self, assembler, user_id, family_id,
    ):
        """Profiles are included when person_names match."""
        profile_data = [
            {
                "name": "张三",
                "relationship": "同事",
                "location": "上海",
                "preferences": {"likes": ["茶"]},
                "favor_balance": 0.0,
                "importance": 7,
                "days_since_contact": 30,
            }
        ]
        with (
            patch.object(
                assembler, "_fetch_person_profiles", return_value=profile_data,
            ),
            patch.object(
                assembler, "_fetch_memory_summaries", return_value=[],
            ),
            patch.object(
                assembler, "_fetch_emotional_trend", return_value=None,
            ),
            patch.object(
                assembler, "_fetch_preference_rules", return_value=[],
            ),
        ):
            ctx = await assembler.assemble(
                user_id, family_id, person_names=["张三"],
            )

        assert len(ctx.person_profiles) == 1
        assert ctx.person_profiles[0]["name"] == "张三"

        xml = ctx.to_prompt_xml()
        assert "<person_profiles>" in xml
        assert "<name>张三</name>" in xml

    @pytest.mark.asyncio
    async def test_assemble_parallel_execution(
        self, assembler, user_id, family_id,
    ):
        """All four fetchers are called via asyncio.gather (parallel)."""
        call_order = []

        async def mock_profiles(*a, **kw):
            call_order.append("profiles")
            return []

        async def mock_summaries(*a, **kw):
            call_order.append("summaries")
            return []

        async def mock_trend(*a, **kw):
            call_order.append("trend")
            return None

        async def mock_rules(*a, **kw):
            call_order.append("rules")
            return []

        with (
            patch.object(assembler, "_fetch_person_profiles", side_effect=mock_profiles),
            patch.object(assembler, "_fetch_memory_summaries", side_effect=mock_summaries),
            patch.object(assembler, "_fetch_emotional_trend", side_effect=mock_trend),
            patch.object(assembler, "_fetch_preference_rules", side_effect=mock_rules),
        ):
            await assembler.assemble(user_id, family_id)

        # All four were called
        assert set(call_order) == {"profiles", "summaries", "trend", "rules"}

    @pytest.mark.asyncio
    async def test_assemble_handles_partial_failure(
        self, assembler, user_id, family_id,
    ):
        """If one fetcher fails, others still return data."""
        profile_data = [{"name": "王五", "importance": 5}]

        async def fail_summaries(*a, **kw):
            raise RuntimeError("DB connection lost")

        with (
            patch.object(
                assembler, "_fetch_person_profiles", return_value=profile_data,
            ),
            patch.object(
                assembler, "_fetch_memory_summaries", side_effect=fail_summaries,
            ),
            patch.object(
                assembler, "_fetch_emotional_trend", return_value=None,
            ),
            patch.object(
                assembler, "_fetch_preference_rules", return_value=[],
            ),
        ):
            ctx = await assembler.assemble(user_id, family_id)

        assert len(ctx.person_profiles) == 1
        assert ctx.memory_summaries == ()  # Failed gracefully

    @pytest.mark.asyncio
    async def test_assemble_no_names_or_locations_returns_empty_profiles(
        self, assembler, user_id, family_id,
    ):
        """When no person_names or locations provided, profiles list is empty."""
        with (
            patch.object(
                assembler, "_fetch_memory_summaries", return_value=[],
            ),
            patch.object(
                assembler, "_fetch_emotional_trend", return_value=None,
            ),
            patch.object(
                assembler, "_fetch_preference_rules", return_value=[],
            ),
        ):
            ctx = await assembler.assemble(user_id, family_id)

        assert ctx.person_profiles == ()

    @pytest.mark.asyncio
    async def test_assemble_static_caches_across_calls(
        self, assembler, user_id, family_id,
    ):
        """Static context is fetched once and cached for repeated calls."""
        summaries = [{"summary_type": "weekly", "title": "t", "content": "c"}]
        call_count = 0

        async def counting_summaries(*a, **kw):
            nonlocal call_count
            call_count += 1
            return summaries

        with (
            patch.object(
                assembler, "_fetch_memory_summaries",
                side_effect=counting_summaries,
            ),
            patch.object(
                assembler, "_fetch_emotional_trend", return_value=None,
            ),
            patch.object(
                assembler, "_fetch_preference_rules", return_value=[],
            ),
        ):
            ctx1 = await assembler.assemble_static(user_id, family_id)
            ctx2 = await assembler.assemble_static(user_id, family_id)

        assert call_count == 1  # Only fetched once
        assert ctx1.memory_summaries == ctx2.memory_summaries
        assert len(ctx1.memory_summaries) == 1
