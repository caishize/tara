"""Tests for Group D optimization items (PLAN-007 through PLAN-011).

PLAN-007: Redis priority calibration cache key uniqueness
PLAN-008: _HINT_MAP expansion to 12+ event types
PLAN-009: mini_curate Level 2 dedup without location
PLAN-010: Insight fallback retry + contextual fields
PLAN-011: Briefing insight generation model downgrade to Haiku
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.curation.services.priority_engine import _redis_cache_key
from src.modules.views.services.timeline_service import TimelineService, _HINT_MAP
from src.modules.insight.insight_content_generator import (
    _build_contextual_fallback,
    _extract_context_fields,
    _MAX_LLM_ATTEMPTS,
    generate_insight_content,
)


# ---------------------------------------------------------------------------
# PLAN-007: Cache key uniqueness
# ---------------------------------------------------------------------------

class TestCacheKeyUniqueness:
    """Two events of the same type in the same family must get distinct keys."""

    def test_different_event_ids_produce_different_keys(self):
        family_id = uuid4()
        event_a = {"event_id": "birthday-mom", "event_type": "birthday",
                    "normalized_start": "2026-03-15"}
        event_b = {"event_id": "birthday-dad", "event_type": "birthday",
                    "normalized_start": "2026-04-20"}

        key_a = _redis_cache_key(event_a, family_id)
        key_b = _redis_cache_key(event_b, family_id)
        assert key_a != key_b

    def test_same_event_same_key(self):
        family_id = uuid4()
        event = {"event_id": "birthday-mom", "event_type": "birthday",
                 "normalized_start": "2026-03-15"}

        key1 = _redis_cache_key(event, family_id)
        key2 = _redis_cache_key(event, family_id)
        assert key1 == key2

    def test_key_includes_event_id_and_date(self):
        family_id = uuid4()
        event = {"event_id": "ev-123", "event_type": "meeting",
                 "normalized_start": "2026-03-01T09:00:00+00:00"}

        key = _redis_cache_key(event, family_id)
        assert "ev-123" in key
        assert "2026-03-01" in key

    def test_missing_start_uses_nodate(self):
        family_id = uuid4()
        event = {"event_id": "ev-no-date", "event_type": "reminder"}

        key = _redis_cache_key(event, family_id)
        assert "nodate" in key


# ---------------------------------------------------------------------------
# PLAN-008: _HINT_MAP expansion
# ---------------------------------------------------------------------------

class TestHintMapExpansion:
    """_HINT_MAP must contain at least 12 entries, all in Chinese."""

    def test_hint_map_has_at_least_12_entries(self):
        assert len(_HINT_MAP) >= 12

    def test_all_hints_are_non_empty_chinese_strings(self):
        for key, hint in _HINT_MAP.items():
            assert isinstance(hint, str)
            assert len(hint) > 0
            # At least one CJK character
            has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in hint)
            assert has_cjk, f"Hint for '{key}' has no CJK characters: {hint}"

    def test_medical_appointment_has_hint(self):
        assert "medical_appointment" in _HINT_MAP
        assert len(_HINT_MAP["medical_appointment"]) > 0

    def test_meeting_has_hint(self):
        assert "meeting" in _HINT_MAP

    def test_flight_has_hint(self):
        assert "flight" in _HINT_MAP

    def test_hint_map_coverage_via_timeline_service(self):
        """Timeline service returns non-empty hint for medical_appointment event."""
        ev = MagicMock()
        ev.event_type = "medical_appointment"
        ev.location = None
        ev.tags = []
        ev.life_context_hint = None
        result = TimelineService._build_life_context_hint(ev)
        assert result is not None
        assert len(result) > 0


# ---------------------------------------------------------------------------
# PLAN-009: Level 2 dedup without location
# ---------------------------------------------------------------------------

class TestDedupNoLocation:
    """Level 2 fingerprint dedup should run even when location is None."""

    @pytest.mark.asyncio
    async def test_level2_dedup_runs_without_location(self):
        """Two identical events (same title, date, no location) should dedup."""
        from src.modules.curation.services.curation_service import SecretaryCurationService
        from src.modules.curation.models import CuratedEvent

        family_id = uuid4()
        user_id = uuid4()
        start_time = datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc)
        title = "周例会"
        event_type = "meeting"

        # Build an existing event with matching fingerprint, properly configured
        existing_event = MagicMock(spec=CuratedEvent)
        existing_event.id = uuid4()
        existing_event.normalized_start = datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc)
        existing_event.normalized_end = datetime(2026, 3, 5, 15, 0, tzinfo=timezone.utc)
        existing_event.original_event_ids = []

        # Mock session
        db = AsyncMock()
        db.commit = AsyncMock()
        # Level 1 (title match): no match
        level1_result = MagicMock()
        level1_result.scalar_one_or_none.return_value = None
        # Level 2 (fingerprint match): match found
        level2_result = MagicMock()
        level2_result.scalar_one_or_none.return_value = existing_event

        db.execute = AsyncMock(side_effect=[level1_result, level2_result])

        service = SecretaryCurationService(db)

        result_event, hints = await service.mini_curate(
            family_id=family_id,
            user_id=user_id,
            title=title,
            event_type=event_type,
            start_time=start_time,
            location=None,  # No location
        )

        # Should have returned the existing event (deduped via Level 2)
        assert result_event is not None
        assert result_event.id == existing_event.id
        # Level 2 query (fingerprint) should have been executed
        assert db.execute.call_count == 2


# ---------------------------------------------------------------------------
# PLAN-010: Insight fallback retry + contextual fields
# ---------------------------------------------------------------------------

class TestInsightFallbackRetry:
    """generate_insight_content retries once before contextual fallback."""

    @pytest.mark.asyncio
    async def test_retries_once_on_first_failure(self):
        """LLM called exactly _MAX_LLM_ATTEMPTS times when all fail."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=RuntimeError("API timeout")
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content(
                "<ctx/>", "birthday",
                person_name="妈妈",
                event_type="生日",
                days_until=3,
            )

        assert mock_client.messages.create.call_count == _MAX_LLM_ATTEMPTS
        # Contextual fallback should include person_name
        assert "妈妈" in result["content"]
        assert "3天" in result["content"]

    @pytest.mark.asyncio
    async def test_succeeds_on_retry(self):
        """First call fails, second call succeeds — only 2 LLM calls made."""
        payload = json.dumps({"title": "生日提醒", "content": "记得准备蛋糕"})

        def _make_response(text):
            block = MagicMock()
            block.text = text
            response = MagicMock()
            response.content = [block]
            return response

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[
                RuntimeError("API timeout"),
                _make_response(payload),
            ]
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content("<ctx/>", "birthday")

        assert mock_client.messages.create.call_count == 2
        assert result["title"] == "生日提醒"
        assert result["content"] == "记得准备蛋糕"

    @pytest.mark.asyncio
    async def test_contextual_fallback_without_explicit_fields(self):
        """Fields extracted from XML when not passed explicitly."""
        context = "<person_name>爸爸</person_name><event_type>体检</event_type><days_until>5</days_until>"
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=RuntimeError("fail")
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content(context, "medical")

        assert "爸爸" in result["content"]
        assert "5天" in result["content"]

    def test_build_contextual_fallback_all_fields(self):
        result = _build_contextual_fallback(
            "温馨提醒", "有件事想提醒你一下。",
            person_name="妈妈", event_type="生日", days_until=3,
        )
        assert "妈妈" in result["content"]
        assert "生日" in result["content"]
        assert "3天" in result["content"]

    def test_build_contextual_fallback_no_fields(self):
        result = _build_contextual_fallback(
            "温馨提醒", "有件事想提醒你一下。",
        )
        assert result["content"] == "有件事想提醒你一下。"

    def test_extract_context_fields_from_xml(self):
        xml = "<person_name>小明</person_name><event_type>考试</event_type><days_until>7</days_until>"
        fields = _extract_context_fields(xml)
        assert fields["person_name"] == "小明"
        assert fields["event_type"] == "考试"
        assert fields["days_until"] == 7


# ---------------------------------------------------------------------------
# PLAN-011: Briefing insight generation model downgrade
# ---------------------------------------------------------------------------

class TestBriefingModelDowngrade:
    """Briefing key insight generation should use Haiku, not Sonnet/GPT-4."""

    @pytest.mark.asyncio
    async def test_key_insights_uses_haiku_client(self):
        """_generate_key_insights calls get_haiku_client, not self.llm (openai)."""
        from src.modules.briefing.services.briefing_generator import BriefingGenerator

        db = AsyncMock()
        gen = BriefingGenerator(db)

        # Mock context collection
        gen._collect_insight_context = AsyncMock(return_value={
            "events": [{"title": "test"}],
            "social_intents": [],
        })
        gen._build_insight_prompt = MagicMock(return_value="prompt text")
        gen._parse_insights = MagicMock(return_value=["insight1"])

        # Build mock Haiku response
        haiku_response = MagicMock()
        block = MagicMock()
        block.text = '["insight1"]'
        haiku_response.content = [block]

        mock_haiku = AsyncMock()
        mock_haiku.messages.create = AsyncMock(return_value=haiku_response)

        # Also mock self.llm to verify it is NOT called
        gen.llm = AsyncMock()

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_haiku,
        ):
            result = await gen._generate_key_insights(uuid4(), [MagicMock()])

        # Haiku client should have been called
        mock_haiku.messages.create.assert_awaited_once()

        # The openai_adapter (self.llm) should NOT have been called
        gen.llm.chat.assert_not_awaited()
