"""Tests for TripCompletenessService - LLM-semantic trip gap detection.

Covers:
- LLM success path with various accommodation_type values
- Cache hit (input_hash match skips LLM)
- LLM unavailable degradation (llm_provider=None)
- LLM exception degradation
- input_hash determinism
- _parse_llm_result correctness
"""
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.services.trip_completeness_service import (
    TripCompletenessResult,
    TripCompletenessService,
    _compute_input_hash,
    _parse_llm_result,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_uuid():
    return uuid.uuid4()


def _make_trip(
    trip_id=None,
    trip_name="Test Trip",
    destination="Tokyo",
    start_date=None,
    end_date=None,
    duration_days=3,
    status="planning",
    category="personal",
    notes=None,
):
    """Create a lightweight trip-like object (no real ORM)."""
    return SimpleNamespace(
        trip_id=trip_id or _make_uuid(),
        trip_name=trip_name,
        destination=destination,
        start_date=start_date or date.today() + timedelta(days=7),
        end_date=end_date or date.today() + timedelta(days=10),
        duration_days=duration_days,
        status=status,
        category=category,
        notes=notes,
    )


def _make_event(
    event_id=None,
    title="Flight to Tokyo",
    event_type="travel",
    location="Tokyo",
    normalized_start=None,
    normalized_end=None,
    status="pending",
    notes=None,
):
    """Create a lightweight curated-event-like object."""
    now = datetime.now(tz=timezone.utc)
    return SimpleNamespace(
        id=event_id or _make_uuid(),
        title=title,
        event_type=event_type,
        location=location,
        normalized_start=normalized_start or now + timedelta(days=7),
        normalized_end=normalized_end or now + timedelta(days=7, hours=3),
        status=status,
        notes=notes,
    )


def _make_llm_response_json(
    has_departure=True,
    has_return=False,
    return_type="missing",
    has_accommodation=False,
    accommodation_type="missing",
    gaps=None,
    reasoning="Test reasoning",
):
    """Build the dict that the LLM would return after JSON parsing."""
    return {
        "has_departure": has_departure,
        "has_return": has_return,
        "return_type": return_type,
        "has_accommodation": has_accommodation,
        "accommodation_type": accommodation_type,
        "gaps": gaps or [],
        "reasoning": reasoning,
    }


def _build_mock_llm_client(llm_json: dict):
    """Build a mock llm client that returns a messages.create response."""
    text_block = MagicMock()
    text_block.text = json.dumps(llm_json)

    response = MagicMock()
    response.content = [text_block]

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# _parse_llm_result (pure function)
# ---------------------------------------------------------------------------

class TestParseLlmResult:
    """Tests for the pure _parse_llm_result helper."""

    def test_all_fields_mapped(self):
        trip_id = _make_uuid()
        raw = _make_llm_response_json(
            has_departure=True,
            has_return=False,
            return_type="missing",
            has_accommodation=True,
            accommodation_type="booked",
            gaps=[{"gap_type": "no_return", "suggestion": "Book return ticket"}],
        )
        result = _parse_llm_result(trip_id, raw, "abc123")

        assert result.trip_id == trip_id
        assert result.has_departure is True
        assert result.has_return is False
        assert result.return_type == "missing"
        assert result.has_accommodation is True
        assert result.accommodation_type == "booked"
        assert len(result.gaps) == 1
        assert result.gaps[0]["gap_type"] == "no_return"
        assert result.input_hash == "abc123"

    def test_defaults_when_keys_missing(self):
        """Missing keys should fall back to safe defaults (treat as complete)."""
        trip_id = _make_uuid()
        result = _parse_llm_result(trip_id, {}, "hash")

        assert result.has_departure is True
        assert result.has_return is True
        assert result.return_type == "explicit"
        assert result.has_accommodation is True
        assert result.accommodation_type == "booked"
        assert result.gaps == []

    def test_frozen_dataclass(self):
        trip_id = _make_uuid()
        result = _parse_llm_result(trip_id, {}, "h")
        with pytest.raises(AttributeError):
            result.has_departure = False


# ---------------------------------------------------------------------------
# _compute_input_hash (pure function)
# ---------------------------------------------------------------------------

class TestComputeInputHash:
    """Tests for the pure _compute_input_hash helper."""

    def test_same_inputs_same_hash(self):
        trip = _make_trip(trip_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        ev = _make_event(event_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))

        hash1 = _compute_input_hash(trip, [ev])
        hash2 = _compute_input_hash(trip, [ev])
        assert hash1 == hash2

    def test_different_events_different_hash(self):
        trip = _make_trip()
        ev_a = _make_event(title="Flight A")
        ev_b = _make_event(title="Flight B")

        hash_a = _compute_input_hash(trip, [ev_a])
        hash_b = _compute_input_hash(trip, [ev_b])
        assert hash_a != hash_b

    def test_different_trip_destination_different_hash(self):
        ev = _make_event()
        trip_a = _make_trip(
            trip_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            destination="Tokyo",
        )
        trip_b = _make_trip(
            trip_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            destination="Osaka",
        )

        assert _compute_input_hash(trip_a, [ev]) != _compute_input_hash(trip_b, [ev])

    def test_hash_is_md5_hex(self):
        trip = _make_trip()
        ev = _make_event()
        h = _compute_input_hash(trip, [ev])

        assert len(h) == 32
        int(h, 16)  # should not raise

    def test_empty_events_list(self):
        trip = _make_trip()
        h = _compute_input_hash(trip, [])
        assert isinstance(h, str)
        assert len(h) == 32


# ---------------------------------------------------------------------------
# TripCompletenessService.check_completeness
# ---------------------------------------------------------------------------

class TestCheckCompleteness:
    """Integration-style tests for the main public method."""

    @pytest.mark.asyncio
    async def test_llm_success_path(self):
        """Happy path: trip found, events found, no cache, LLM returns valid JSON."""
        trip_id = _make_uuid()
        family_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)
        events = [_make_event(), _make_event(title="Hotel Check-in")]

        llm_json = _make_llm_response_json(
            has_departure=True,
            has_return=False,
            return_type="missing",
            has_accommodation=True,
            accommodation_type="booked",
            gaps=[
                {"gap_type": "no_return", "suggestion": "Book return", "urgency": "high"}
            ],
        )
        llm_client = _build_mock_llm_client(llm_json)

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        # Mock _load_trip_events to return our events
        service = TripCompletenessService(db, llm_provider=llm_client)
        service._load_trip_events = AsyncMock(return_value=events)
        service._load_trip_itineraries = AsyncMock(return_value=[])
        service._load_cached_result = AsyncMock(return_value=None)
        service._save_check_result = AsyncMock()
        service._create_prep_items_for_gaps = AsyncMock()
        service._cleanup_stale_prep_items = AsyncMock()

        result = await service.check_completeness(trip_id, family_id)

        assert result is not None
        assert isinstance(result, TripCompletenessResult)
        assert result.trip_id == trip_id
        assert result.has_departure is True
        assert result.has_return is False
        assert result.return_type == "missing"
        assert result.has_accommodation is True
        assert result.accommodation_type == "booked"
        assert len(result.gaps) == 1

        llm_client.messages.create.assert_awaited_once()
        service._save_check_result.assert_awaited_once()
        service._create_prep_items_for_gaps.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self):
        """When cached result matches input_hash, LLM should not be called."""
        trip_id = _make_uuid()
        family_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)
        events = [_make_event()]

        cached_result = TripCompletenessResult(
            trip_id=trip_id,
            has_departure=True,
            has_return=True,
            return_type="explicit",
            has_accommodation=True,
            accommodation_type="booked",
            gaps=[],
            input_hash="cached_hash",
        )

        llm_client = _build_mock_llm_client({})

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        service = TripCompletenessService(db, llm_provider=llm_client)
        service._load_trip_events = AsyncMock(return_value=events)
        service._load_trip_itineraries = AsyncMock(return_value=[])
        service._load_cached_result = AsyncMock(return_value=cached_result)
        service._cleanup_stale_prep_items = AsyncMock()

        result = await service.check_completeness(trip_id, family_id)

        assert result is cached_result
        llm_client.messages.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_llm_provider_none_returns_none(self):
        """When llm_provider is None and no cache, returns None (fallback signal)."""
        trip_id = _make_uuid()
        family_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)
        events = [_make_event()]

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        service = TripCompletenessService(db, llm_provider=None)
        service._load_trip_events = AsyncMock(return_value=events)
        service._load_trip_itineraries = AsyncMock(return_value=[])
        service._load_cached_result = AsyncMock(return_value=None)

        result = await service.check_completeness(trip_id, family_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_exception_returns_none(self):
        """When LLM raises an exception, service degrades gracefully to None."""
        trip_id = _make_uuid()
        family_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)
        events = [_make_event()]

        llm_client = MagicMock()
        llm_client.messages = MagicMock()
        llm_client.messages.create = AsyncMock(
            side_effect=RuntimeError("LLM timeout")
        )

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        service = TripCompletenessService(db, llm_provider=llm_client)
        service._load_trip_events = AsyncMock(return_value=events)
        service._load_trip_itineraries = AsyncMock(return_value=[])
        service._load_cached_result = AsyncMock(return_value=None)

        result = await service.check_completeness(trip_id, family_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json_returns_none(self):
        """When LLM returns non-JSON text, _call_llm_check returns None."""
        trip_id = _make_uuid()
        family_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)
        events = [_make_event()]

        text_block = MagicMock()
        text_block.text = "This is not valid JSON"
        response = MagicMock()
        response.content = [text_block]

        llm_client = MagicMock()
        llm_client.messages = MagicMock()
        llm_client.messages.create = AsyncMock(return_value=response)

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        service = TripCompletenessService(db, llm_provider=llm_client)
        service._load_trip_events = AsyncMock(return_value=events)
        service._load_trip_itineraries = AsyncMock(return_value=[])
        service._load_cached_result = AsyncMock(return_value=None)

        result = await service.check_completeness(trip_id, family_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_trip_not_found_returns_none(self):
        """When trip does not exist in DB, returns None."""
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        service = TripCompletenessService(db, llm_provider=MagicMock())
        result = await service.check_completeness(_make_uuid(), _make_uuid())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_events_returns_none(self):
        """When trip has no associated curated events, returns None."""
        trip_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        service = TripCompletenessService(db)
        service._load_trip_events = AsyncMock(return_value=[])

        result = await service.check_completeness(trip_id, _make_uuid())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_gaps_does_not_create_prep_items(self):
        """When LLM finds no gaps, _create_prep_items_for_gaps should not be called."""
        trip_id = _make_uuid()
        family_id = _make_uuid()
        trip = _make_trip(trip_id=trip_id)
        events = [_make_event()]

        llm_json = _make_llm_response_json(
            has_departure=True,
            has_return=True,
            return_type="explicit",
            has_accommodation=True,
            accommodation_type="booked",
            gaps=[],
        )
        llm_client = _build_mock_llm_client(llm_json)

        db = AsyncMock()
        db.get = AsyncMock(return_value=trip)

        service = TripCompletenessService(db, llm_provider=llm_client)
        service._load_trip_events = AsyncMock(return_value=events)
        service._load_trip_itineraries = AsyncMock(return_value=[])
        service._load_cached_result = AsyncMock(return_value=None)
        service._save_check_result = AsyncMock()
        service._create_prep_items_for_gaps = AsyncMock()
        service._cleanup_stale_prep_items = AsyncMock()

        result = await service.check_completeness(trip_id, family_id)

        assert result is not None
        assert result.gaps == []
        service._create_prep_items_for_gaps.assert_not_awaited()


# ---------------------------------------------------------------------------
# Accommodation types
# ---------------------------------------------------------------------------

class TestAccommodationTypes:
    """Verify various accommodation_type values are correctly propagated."""

    @pytest.mark.parametrize(
        "accommodation_type",
        ["booked", "private", "missing"],
    )
    def test_accommodation_types(self, accommodation_type):
        trip_id = _make_uuid()
        raw = _make_llm_response_json(accommodation_type=accommodation_type)
        result = _parse_llm_result(trip_id, raw, "hash")
        assert result.accommodation_type == accommodation_type

    @pytest.mark.parametrize(
        "return_type",
        ["explicit", "same_day", "missing"],
    )
    def test_return_types(self, return_type):
        trip_id = _make_uuid()
        raw = _make_llm_response_json(return_type=return_type)
        result = _parse_llm_result(trip_id, raw, "hash")
        assert result.return_type == return_type


# ---------------------------------------------------------------------------
# _call_llm_check fallback to AsyncAnthropic
# ---------------------------------------------------------------------------

class TestCallLlmCheckFallback:
    """Verify that _call_llm_check creates a new AsyncAnthropic when the
    injected provider lacks .messages."""

    @pytest.mark.asyncio
    async def test_fallback_when_no_messages_attr(self):
        """Provider without .messages should trigger AsyncAnthropic fallback."""
        trip = _make_trip()
        events = [_make_event()]

        # Provider has no .messages attribute
        bare_provider = object()

        db = AsyncMock()
        service = TripCompletenessService(db, llm_provider=bare_provider)

        llm_json = _make_llm_response_json()
        text_block = MagicMock()
        text_block.text = json.dumps(llm_json)
        mock_response = MagicMock()
        mock_response.content = [text_block]

        with patch(
            "anthropic.AsyncAnthropic"
        ) as MockAnthropic:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockAnthropic.return_value = mock_client

            result = await service._call_llm_check(trip, events)

        assert result is not None
        assert result["has_departure"] is True
        MockAnthropic.assert_called_once()
