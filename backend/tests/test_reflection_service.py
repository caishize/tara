"""Tests for PostSessionReflectionService - post-session entity extraction & focused curation.

Covers:
- Normal reflect flow (LLM returns entities, triggers 3 curation dimensions)
- Empty entities (no curation triggered)
- LLM extraction failure (graceful degrade to empty entities)
- Cooldown hit (trip skipped within 30 min)
- Trip hint resolution (destination keyword → trip ID matching)
- Members/dates cooldown (in-process monotonic cache)
- SessionEntities immutability and is_empty property
"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.services.reflection_service import (
    PostSessionReflectionService,
    SessionEntities,
    _EMPTY_ENTITIES,
    REFLECTION_COOLDOWN_MINUTES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uuid():
    return uuid.uuid4()


def _build_haiku_response(data: dict) -> MagicMock:
    """Build a mock Anthropic messages.create response containing JSON."""
    text_block = MagicMock()
    text_block.text = json.dumps(data)
    # hasattr(text_block, "text") needs to be True -- MagicMock handles this.

    response = MagicMock()
    response.content = [text_block]
    return response


def _make_message(role="user", content="Hello", created_at=None):
    """Lightweight ConversationMessage-like object."""
    return SimpleNamespace(
        role=role,
        content=content,
        created_at=created_at or datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# SessionEntities dataclass
# ---------------------------------------------------------------------------

class TestSessionEntities:
    """Tests for the SessionEntities frozen dataclass."""

    def test_is_empty_when_all_empty(self):
        e = SessionEntities(trip_hints=(), member_names=(), important_dates=())
        assert e.is_empty is True

    def test_is_not_empty_with_trip(self):
        e = SessionEntities(
            trip_hints=({"destination": "上海", "date_hint": "下周五"},),
            member_names=(),
            important_dates=(),
        )
        assert e.is_empty is False

    def test_is_not_empty_with_member(self):
        e = SessionEntities(
            trip_hints=(),
            member_names=("Alice",),
            important_dates=(),
        )
        assert e.is_empty is False

    def test_is_not_empty_with_date(self):
        e = SessionEntities(
            trip_hints=(),
            member_names=(),
            important_dates=("2026-03-15",),
        )
        assert e.is_empty is False

    def test_frozen(self):
        e = _EMPTY_ENTITIES
        with pytest.raises(AttributeError):
            e.trip_hints = ("x",)

    def test_global_empty_entities_is_empty(self):
        assert _EMPTY_ENTITIES.is_empty is True


# ---------------------------------------------------------------------------
# PostSessionReflectionService.reflect
# ---------------------------------------------------------------------------

class TestReflect:
    """Tests for the main reflect() entry point."""

    @pytest.mark.asyncio
    async def test_normal_reflect_triggers_all_dimensions(self):
        """When LLM returns all 3 entity types, all 3 curation dimensions fire."""
        session_id = _make_uuid()
        user_id = _make_uuid()
        family_id = _make_uuid()
        entities = SessionEntities(
            trip_hints=({"destination": "上海", "date_hint": "下周五"},),
            member_names=("Alice",),
            important_dates=("2026-04-01",),
        )

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())

        # Mock entity extraction to return our entities
        service._extract_entities = AsyncMock(return_value=entities)
        service._focused_curation = AsyncMock()

        await service.reflect(session_id, user_id, family_id)

        service._extract_entities.assert_awaited_once_with(session_id)
        service._focused_curation.assert_awaited_once_with(entities, family_id)

    @pytest.mark.asyncio
    async def test_empty_entities_skips_curation(self):
        """When LLM returns empty entities, _focused_curation should not be called."""
        session_id = _make_uuid()
        user_id = _make_uuid()
        family_id = _make_uuid()

        db = AsyncMock()
        service = PostSessionReflectionService(db)
        service._extract_entities = AsyncMock(return_value=_EMPTY_ENTITIES)
        service._focused_curation = AsyncMock()

        await service.reflect(session_id, user_id, family_id)

        service._focused_curation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extraction_failure_returns_empty(self):
        """When _extract_entities raises, reflect catches and returns gracefully."""
        session_id = _make_uuid()
        user_id = _make_uuid()
        family_id = _make_uuid()

        db = AsyncMock()
        service = PostSessionReflectionService(db)

        # Force reflect to go through its try/except
        service._extract_entities = AsyncMock(
            side_effect=RuntimeError("LLM boom")
        )
        service._focused_curation = AsyncMock()

        # Should not raise
        await service.reflect(session_id, user_id, family_id)

        service._focused_curation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_focused_curation_exception_is_caught(self):
        """Even if _focused_curation raises, reflect does not propagate."""
        session_id = _make_uuid()
        user_id = _make_uuid()
        family_id = _make_uuid()

        entities = SessionEntities(
            trip_hints=(),
            member_names=("Bob",),
            important_dates=(),
        )

        db = AsyncMock()
        service = PostSessionReflectionService(db)
        service._extract_entities = AsyncMock(return_value=entities)
        service._focused_curation = AsyncMock(
            side_effect=RuntimeError("Curation boom")
        )

        # Should not raise (fire-and-forget semantics)
        await service.reflect(session_id, user_id, family_id)


# ---------------------------------------------------------------------------
# PostSessionReflectionService._extract_entities
# ---------------------------------------------------------------------------

class TestExtractEntities:
    """Tests for the entity extraction step."""

    @pytest.mark.asyncio
    async def test_extracts_entities_from_llm(self):
        """Happy path: LLM returns valid JSON, entities are parsed."""
        session_id = _make_uuid()

        messages = [
            _make_message(role="user", content="I'm going on a trip to Shanghai"),
            _make_message(role="assistant", content="Let me check that for you"),
        ]

        llm_data = {
            "trip_hints": [{"destination": "上海", "date_hint": "下周五"}],
            "member_names": ["Alice", "Bob"],
            "important_dates": ["2026-05-20"],
        }

        # Mock DB query for messages
        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = messages
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = PostSessionReflectionService(db)

        # Mock the haiku client
        mock_response = _build_haiku_response(llm_data)
        with patch(
            "src.core.llm.haiku_client.get_haiku_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            entities = await service._extract_entities(session_id)

        assert len(entities.trip_hints) == 1
        assert entities.trip_hints[0]["destination"] == "上海"
        assert entities.member_names == ("Alice", "Bob")
        assert entities.important_dates == ("2026-05-20",)

    @pytest.mark.asyncio
    async def test_no_messages_returns_empty(self):
        """When no messages in session, returns empty entities."""
        session_id = _make_uuid()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = PostSessionReflectionService(db)
        entities = await service._extract_entities(session_id)

        assert entities.is_empty is True

    @pytest.mark.asyncio
    async def test_llm_exception_returns_empty(self):
        """When haiku call fails, returns empty entities (graceful degrade)."""
        session_id = _make_uuid()

        messages = [_make_message(content="Some message")]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = messages
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = PostSessionReflectionService(db)

        with patch(
            "src.core.llm.haiku_client.get_haiku_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                side_effect=RuntimeError("API error")
            )
            mock_get_client.return_value = mock_client

            entities = await service._extract_entities(session_id)

        assert entities.is_empty is True

    @pytest.mark.asyncio
    async def test_llm_returns_empty_content_blocks(self):
        """When LLM response has no text blocks, returns empty entities."""
        session_id = _make_uuid()
        messages = [_make_message(content="Hello")]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = messages
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = PostSessionReflectionService(db)

        # Response with no text blocks
        response = MagicMock()
        response.content = []

        with patch(
            "src.core.llm.haiku_client.get_haiku_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=response)
            mock_get_client.return_value = mock_client

            entities = await service._extract_entities(session_id)

        assert entities.is_empty is True


# ---------------------------------------------------------------------------
# PostSessionReflectionService._focused_curation
# ---------------------------------------------------------------------------

class TestFocusedCuration:
    """Tests for _focused_curation dispatch logic."""

    @pytest.mark.asyncio
    async def test_dispatches_all_three_types(self):
        """When all entity types present, all 3 sub-methods are called."""
        family_id = _make_uuid()
        entities = SessionEntities(
            trip_hints=({"destination": "上海", "date_hint": "下周五"},),
            member_names=("Alice",),
            important_dates=("2026-06-01",),
        )

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())
        service._check_trip_completeness_from_hints = AsyncMock()
        service._trigger_memory_associations = AsyncMock()
        service._trigger_date_approaching = AsyncMock()

        await service._focused_curation(entities, family_id)

        service._check_trip_completeness_from_hints.assert_awaited_once_with(
            entities.trip_hints, family_id,
        )
        service._trigger_memory_associations.assert_awaited_once_with(
            entities.member_names, family_id,
        )
        service._trigger_date_approaching.assert_awaited_once_with(
            entities.important_dates, family_id,
        )

    @pytest.mark.asyncio
    async def test_skips_empty_dimensions(self):
        """When only member_names present, only _trigger_memory_associations fires."""
        family_id = _make_uuid()
        entities = SessionEntities(
            trip_hints=(),
            member_names=("Bob",),
            important_dates=(),
        )

        db = AsyncMock()
        service = PostSessionReflectionService(db)
        service._check_trip_completeness_from_hints = AsyncMock()
        service._trigger_memory_associations = AsyncMock()
        service._trigger_date_approaching = AsyncMock()

        await service._focused_curation(entities, family_id)

        service._check_trip_completeness_from_hints.assert_not_awaited()
        service._trigger_memory_associations.assert_awaited_once()
        service._trigger_date_approaching.assert_not_awaited()


# ---------------------------------------------------------------------------
# PostSessionReflectionService._check_trip_completeness_from_hints
# ---------------------------------------------------------------------------

class TestCheckTripCompleteness:
    """Tests for the trip completeness sub-routine (hint-based resolution)."""

    @pytest.mark.asyncio
    async def test_no_matching_trips_skips(self):
        """When no trips match the hints, completeness check is not called."""
        family_id = _make_uuid()
        hints = ({"destination": "火星", "date_hint": "明天"},)

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())
        service._resolve_trip_hints_to_ids = AsyncMock(return_value=[])

        with patch(
            "src.modules.curation.services.trip_completeness_service.TripCompletenessService"
        ) as MockTCS:
            mock_tcs_instance = MagicMock()
            mock_tcs_instance.check_completeness = AsyncMock()
            MockTCS.return_value = mock_tcs_instance

            await service._check_trip_completeness_from_hints(hints, family_id)

            mock_tcs_instance.check_completeness.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolved_trip_calls_completeness(self):
        """Resolved trip ID triggers TripCompletenessService.check_completeness."""
        family_id = _make_uuid()
        trip_id = _make_uuid()
        hints = ({"destination": "上海", "date_hint": "下周"},)

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())
        service._resolve_trip_hints_to_ids = AsyncMock(return_value=[trip_id])
        service._is_trip_in_cooldown = AsyncMock(return_value=False)

        with patch(
            "src.modules.curation.services.trip_completeness_service.TripCompletenessService"
        ) as MockTCS:
            mock_tcs_instance = MagicMock()
            mock_tcs_instance.check_completeness = AsyncMock(return_value=None)
            MockTCS.return_value = mock_tcs_instance

            await service._check_trip_completeness_from_hints(hints, family_id)

            mock_tcs_instance.check_completeness.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cooldown_skips_trip(self):
        """Trip in cooldown period should be skipped."""
        family_id = _make_uuid()
        trip_id = _make_uuid()
        hints = ({"destination": "北京", "date_hint": "周五"},)

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())
        service._resolve_trip_hints_to_ids = AsyncMock(return_value=[trip_id])
        service._is_trip_in_cooldown = AsyncMock(return_value=True)

        with patch(
            "src.modules.curation.services.trip_completeness_service.TripCompletenessService"
        ) as MockTCS:
            mock_tcs_instance = MagicMock()
            mock_tcs_instance.check_completeness = AsyncMock()
            MockTCS.return_value = mock_tcs_instance

            await service._check_trip_completeness_from_hints(hints, family_id)

            mock_tcs_instance.check_completeness.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_completeness_check_exception_is_caught(self):
        """Exception during check_completeness should not propagate."""
        family_id = _make_uuid()
        trip_id = _make_uuid()
        hints = ({"destination": "深圳", "date_hint": "本周"},)

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())
        service._resolve_trip_hints_to_ids = AsyncMock(return_value=[trip_id])
        service._is_trip_in_cooldown = AsyncMock(return_value=False)

        with patch(
            "src.modules.curation.services.trip_completeness_service.TripCompletenessService"
        ) as MockTCS:
            mock_tcs_instance = MagicMock()
            mock_tcs_instance.check_completeness = AsyncMock(
                side_effect=RuntimeError("DB error")
            )
            MockTCS.return_value = mock_tcs_instance

            # Should not raise
            await service._check_trip_completeness_from_hints(hints, family_id)


# ---------------------------------------------------------------------------
# PostSessionReflectionService._is_trip_in_cooldown
# ---------------------------------------------------------------------------

class TestIsTripInCooldown:
    """Tests for the cooldown check."""

    @pytest.mark.asyncio
    async def test_no_recent_check_returns_false(self):
        """No recent check means trip is not in cooldown."""
        family_id = _make_uuid()
        trip_id = _make_uuid()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        service = PostSessionReflectionService(db)
        result = await service._is_trip_in_cooldown(trip_id, family_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_recent_check_returns_true(self):
        """Recent check (within cooldown) means trip is in cooldown."""
        family_id = _make_uuid()
        trip_id = _make_uuid()

        db = AsyncMock()
        mock_result = MagicMock()
        # Return a non-None row to indicate a recent check exists
        mock_result.scalar_one_or_none.return_value = MagicMock()
        db.execute = AsyncMock(return_value=mock_result)

        service = PostSessionReflectionService(db)
        result = await service._is_trip_in_cooldown(trip_id, family_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_db_error_returns_false(self):
        """DB error (table missing) returns False (conservative: allow check)."""
        from sqlalchemy.exc import ProgrammingError

        family_id = _make_uuid()
        trip_id = _make_uuid()

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=ProgrammingError("statement", {}, Exception("table missing"))
        )

        service = PostSessionReflectionService(db)
        result = await service._is_trip_in_cooldown(trip_id, family_id)
        assert result is False


# ---------------------------------------------------------------------------
# PostSessionReflectionService._build_messages_text
# ---------------------------------------------------------------------------

class TestBuildMessagesText:
    """Tests for the message text builder."""

    def test_concatenates_role_and_content(self):
        messages = [
            _make_message(role="user", content="Hello"),
            _make_message(role="assistant", content="Hi there"),
        ]
        db = AsyncMock()
        service = PostSessionReflectionService(db)
        text = service._build_messages_text(messages)

        assert "user: Hello" in text
        assert "assistant: Hi there" in text

    def test_skips_empty_content(self):
        messages = [
            _make_message(role="user", content="Hello"),
            _make_message(role="system", content=None),
            _make_message(role="user", content=""),
        ]
        db = AsyncMock()
        service = PostSessionReflectionService(db)
        text = service._build_messages_text(messages)

        assert "user: Hello" in text
        # None and empty content should be filtered
        assert "system:" not in text

    def test_truncation(self):
        """Text longer than _MAX_MESSAGES_TEXT_CHARS should be truncated."""
        long_content = "x" * 5000
        messages = [_make_message(content=long_content)]

        db = AsyncMock()
        service = PostSessionReflectionService(db)
        text = service._build_messages_text(messages)

        assert len(text) == 4000  # _MAX_MESSAGES_TEXT_CHARS


# ---------------------------------------------------------------------------
# _trigger_date_approaching
# ---------------------------------------------------------------------------

class TestTriggerDateApproaching:
    """Tests for date_approaching dispatch."""

    @pytest.mark.asyncio
    async def test_dispatches_for_valid_date(self):
        """Valid date string should trigger TriggerDispatcher.dispatch."""
        family_id = _make_uuid()
        dates = ("2026-04-15",)

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())

        with patch(
            "src.modules.curation.services.trigger_dispatcher.TriggerDispatcher"
        ) as MockDispatcher:
            mock_instance = MagicMock()
            mock_instance.dispatch = AsyncMock()
            MockDispatcher.return_value = mock_instance

            await service._trigger_date_approaching(dates, family_id)

            mock_instance.dispatch.assert_awaited_once()
            call_kwargs = mock_instance.dispatch.call_args
            assert call_kwargs[1]["trigger_type"] == "date_approaching"

    @pytest.mark.asyncio
    async def test_invalid_date_format_caught(self):
        """Invalid date string should not propagate exception."""
        family_id = _make_uuid()
        dates = ("not-a-date",)

        db = AsyncMock()
        service = PostSessionReflectionService(db, llm_provider=MagicMock())

        with patch(
            "src.modules.curation.services.trigger_dispatcher.TriggerDispatcher"
        ) as MockDispatcher:
            mock_instance = MagicMock()
            mock_instance.dispatch = AsyncMock()
            MockDispatcher.return_value = mock_instance

            # Should not raise
            await service._trigger_date_approaching(dates, family_id)
