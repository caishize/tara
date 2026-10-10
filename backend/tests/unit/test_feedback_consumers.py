"""Tests for the 4 FeedbackBus consumers.

Uses a mock FamilyPreferenceRepository to avoid DB dependencies
while verifying the consumer logic (weight adjustments, suppression,
EMA smoothing, etc.).
"""

from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.core.feedback.feedback_bus import (
    FeedbackBus,
    FeedbackConsumer,
    FeedbackEvent,
    FeedbackSignal,
)
from src.core.feedback.consumers.priority_feedback_consumer import (
    PriorityFeedbackConsumer,
    _CANCEL_DECAY,
    _DEFAULT_SEVERITY,
    _MIN_SEVERITY,
    _RESCHEDULE_DECAY,
)
from src.core.feedback.consumers.association_feedback_consumer import (
    AssociationFeedbackConsumer,
    _DEFAULT_WEIGHT,
    _HELPFUL_BOOST,
    _INITIATED_BOOST,
    _MAX_WEIGHT,
    _MIN_WEIGHT,
    _SKIPPED_PENALTY,
)
from src.core.feedback.consumers.recommendation_feedback_consumer import (
    RecommendationFeedbackConsumer,
    _DISMISSED_MULTIPLIER,
    _DISMISS_STREAK_THRESHOLD,
    _IGNORE_SUPPRESS_THRESHOLD,
    _IGNORED_MULTIPLIER,
    _USEFUL_MULTIPLIER,
)
from src.core.feedback.consumers.buffer_time_feedback_consumer import (
    BufferTimeFeedbackConsumer,
    _DEFAULT_BUFFER,
    _EMA_ALPHA,
)


# ---------------------------------------------------------------------------
# Shared mock infrastructure
# ---------------------------------------------------------------------------

class FakeFamilyPreference:
    """Mimics the FamilyPreference ORM model for testing."""

    def __init__(
        self,
        family_id=None,
        event_type_severity=None,
        association_weights=None,
        recommendation_weights=None,
        suppressed_types=None,
        buffer_minutes=None,
        priority_weights=None,
    ):
        self.family_id = family_id or uuid4()
        self.event_type_severity = event_type_severity or {}
        self.association_weights = association_weights or {}
        self.recommendation_weights = recommendation_weights or {}
        self.suppressed_types = suppressed_types or []
        self.buffer_minutes = buffer_minutes or {}
        self.priority_weights = priority_weights or {}
        self.updated_at = None


class FakeRepo:
    """In-memory FamilyPreferenceRepository for testing."""

    def __init__(self, pref: FakeFamilyPreference):
        self._pref = pref
        self.update_calls: List[tuple] = []
        self.suppress_calls: List[str] = []

    async def get_or_create_default(self, family_id):
        return self._pref

    async def get_by_family_id(self, family_id):
        return self._pref

    async def update_weights(self, family_id, field, updates):
        self.update_calls.append((field, updates))
        current = getattr(self._pref, field) or {}
        merged = {**current, **updates}
        setattr(self._pref, field, merged)
        return self._pref

    async def add_suppressed_type(self, family_id, type_name):
        self.suppress_calls.append(type_name)
        current = list(self._pref.suppressed_types or [])
        if type_name not in current:
            self._pref.suppressed_types = [*current, type_name]

    async def remove_suppressed_type(self, family_id, type_name):
        current = list(self._pref.suppressed_types or [])
        self._pref.suppressed_types = [t for t in current if t != type_name]


def _make_event(signal: FeedbackSignal, data: dict, family_id=None) -> FeedbackEvent:
    return FeedbackEvent(
        signal=signal,
        family_id=family_id or uuid4(),
        user_id=uuid4(),
        data=data,
        source="test",
    )


def _make_session_factory():
    """Create a mock async_sessionmaker that returns an AsyncMock session."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    return MagicMock(return_value=mock_session)


# ---------------------------------------------------------------------------
# PriorityFeedbackConsumer tests
# ---------------------------------------------------------------------------

class TestPriorityFeedbackConsumer:

    @pytest.fixture()
    def setup(self):
        pref = FakeFamilyPreference()
        repo = FakeRepo(pref)
        db = _make_session_factory()
        consumer = PriorityFeedbackConsumer(db)
        consumer._get_repo = AsyncMock(return_value=repo)
        return consumer, pref, repo

    def test_protocol_conformance(self):
        db = _make_session_factory()
        consumer = PriorityFeedbackConsumer(db)
        assert isinstance(consumer, FeedbackConsumer)
        assert FeedbackSignal.EVENT_RESCHEDULED in consumer.consumes_signals
        assert FeedbackSignal.EVENT_CANCELLED in consumer.consumes_signals
        assert FeedbackSignal.PRIORITY_OVERRIDE in consumer.consumes_signals

    @pytest.mark.asyncio
    async def test_rescheduled_decays_severity(self, setup):
        consumer, pref, repo = setup
        pref.event_type_severity = {"meeting": 0.5}

        event = _make_event(
            FeedbackSignal.EVENT_RESCHEDULED,
            {"event_type": "meeting"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        expected = round(0.5 * _RESCHEDULE_DECAY, 4)
        assert pref.event_type_severity["meeting"] == expected

    @pytest.mark.asyncio
    async def test_cancelled_decays_more(self, setup):
        consumer, pref, repo = setup
        pref.event_type_severity = {"meeting": 0.5}

        event = _make_event(
            FeedbackSignal.EVENT_CANCELLED,
            {"event_type": "meeting"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        expected = round(0.5 * _CANCEL_DECAY, 4)
        assert pref.event_type_severity["meeting"] == expected

    @pytest.mark.asyncio
    async def test_new_event_type_uses_default(self, setup):
        consumer, pref, repo = setup
        pref.event_type_severity = {}

        event = _make_event(
            FeedbackSignal.EVENT_RESCHEDULED,
            {"event_type": "webinar"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        expected = round(_DEFAULT_SEVERITY * _RESCHEDULE_DECAY, 4)
        assert pref.event_type_severity["webinar"] == expected

    @pytest.mark.asyncio
    async def test_severity_floor(self, setup):
        consumer, pref, repo = setup
        pref.event_type_severity = {"meeting": _MIN_SEVERITY}

        event = _make_event(
            FeedbackSignal.EVENT_CANCELLED,
            {"event_type": "meeting"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.event_type_severity["meeting"] >= _MIN_SEVERITY

    @pytest.mark.asyncio
    async def test_priority_override_higher(self, setup):
        consumer, pref, repo = setup
        pref.event_type_severity = {"medical": 0.5}

        event = _make_event(
            FeedbackSignal.PRIORITY_OVERRIDE,
            {"event_type": "medical", "old_priority": 3, "new_priority": 8},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.event_type_severity["medical"] > 0.5

    @pytest.mark.asyncio
    async def test_priority_override_lower(self, setup):
        consumer, pref, repo = setup
        pref.event_type_severity = {"meeting": 0.8}

        event = _make_event(
            FeedbackSignal.PRIORITY_OVERRIDE,
            {"event_type": "meeting", "old_priority": 8, "new_priority": 3},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.event_type_severity["meeting"] < 0.8

    @pytest.mark.asyncio
    async def test_missing_event_type_is_noop(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.EVENT_RESCHEDULED,
            {},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert len(repo.update_calls) == 0


# ---------------------------------------------------------------------------
# AssociationFeedbackConsumer tests
# ---------------------------------------------------------------------------

class TestAssociationFeedbackConsumer:

    @pytest.fixture()
    def setup(self):
        pref = FakeFamilyPreference()
        repo = FakeRepo(pref)
        db = _make_session_factory()
        consumer = AssociationFeedbackConsumer(db)
        consumer._get_repo = AsyncMock(return_value=repo)
        return consumer, pref, repo

    def test_protocol_conformance(self):
        db = _make_session_factory()
        consumer = AssociationFeedbackConsumer(db)
        assert isinstance(consumer, FeedbackConsumer)
        assert FeedbackSignal.CONTACT_INITIATED in consumer.consumes_signals
        assert FeedbackSignal.CONTACT_SKIPPED in consumer.consumes_signals
        assert FeedbackSignal.ANNOTATION_HELPFUL in consumer.consumes_signals

    @pytest.mark.asyncio
    async def test_contact_initiated_boosts(self, setup):
        consumer, pref, repo = setup
        pref.association_weights = {"stale_contact": 1.0}

        event = _make_event(
            FeedbackSignal.CONTACT_INITIATED,
            {"association_type": "stale_contact"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        expected = round(1.0 + _INITIATED_BOOST, 4)
        assert pref.association_weights["stale_contact"] == expected

    @pytest.mark.asyncio
    async def test_contact_skipped_penalizes(self, setup):
        consumer, pref, repo = setup
        pref.association_weights = {"stale_contact": 1.0}

        event = _make_event(
            FeedbackSignal.CONTACT_SKIPPED,
            {"association_type": "stale_contact"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        expected = round(1.0 - _SKIPPED_PENALTY, 4)
        assert pref.association_weights["stale_contact"] == expected

    @pytest.mark.asyncio
    async def test_annotation_helpful_uses_prefix(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.ANNOTATION_HELPFUL,
            {"annotation_type": "preparation_hint"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        key = "annotation:preparation_hint"
        expected = round(_DEFAULT_WEIGHT + _HELPFUL_BOOST, 4)
        assert pref.association_weights[key] == expected

    @pytest.mark.asyncio
    async def test_weight_capped_at_max(self, setup):
        consumer, pref, repo = setup
        pref.association_weights = {"stale_contact": 1.95}

        event = _make_event(
            FeedbackSignal.CONTACT_INITIATED,
            {"association_type": "stale_contact"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.association_weights["stale_contact"] <= _MAX_WEIGHT

    @pytest.mark.asyncio
    async def test_weight_floored_at_min(self, setup):
        consumer, pref, repo = setup
        pref.association_weights = {"stale_contact": 0.15}

        event = _make_event(
            FeedbackSignal.CONTACT_SKIPPED,
            {"association_type": "stale_contact"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.association_weights["stale_contact"] >= _MIN_WEIGHT

    @pytest.mark.asyncio
    async def test_missing_association_type_is_noop(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.CONTACT_INITIATED,
            {},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert len(repo.update_calls) == 0


# ---------------------------------------------------------------------------
# RecommendationFeedbackConsumer tests
# ---------------------------------------------------------------------------

class TestRecommendationFeedbackConsumer:

    @pytest.fixture()
    def setup(self):
        pref = FakeFamilyPreference()
        repo = FakeRepo(pref)
        db = _make_session_factory()
        consumer = RecommendationFeedbackConsumer(db)
        consumer._get_repo = AsyncMock(return_value=repo)
        return consumer, pref, repo

    def test_protocol_conformance(self):
        db = _make_session_factory()
        consumer = RecommendationFeedbackConsumer(db)
        assert isinstance(consumer, FeedbackConsumer)
        signals = consumer.consumes_signals
        assert FeedbackSignal.INSIGHT_USEFUL in signals
        assert FeedbackSignal.INSIGHT_IGNORED in signals
        assert FeedbackSignal.INSIGHT_NEVER_AGAIN in signals
        assert FeedbackSignal.SUGGESTION_ACTED in signals
        assert FeedbackSignal.SUGGESTION_DISMISSED in signals

    @pytest.mark.asyncio
    async def test_insight_useful_boosts_weight(self, setup):
        consumer, pref, repo = setup
        pref.recommendation_weights = {
            "follow_up": {"weight": 1.0, "shown_count": 0, "ignore_count": 0, "dismiss_streak": 0},
        }

        event = _make_event(
            FeedbackSignal.INSIGHT_USEFUL,
            {"insight_type": "follow_up"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        stats = pref.recommendation_weights["follow_up"]
        assert stats["weight"] == pytest.approx(1.0 * _USEFUL_MULTIPLIER, abs=0.01)
        assert stats["shown_count"] == 1
        assert stats["dismiss_streak"] == 0

    @pytest.mark.asyncio
    async def test_insight_useful_resets_dismiss_streak(self, setup):
        consumer, pref, repo = setup
        pref.recommendation_weights = {
            "follow_up": {"weight": 0.8, "shown_count": 3, "ignore_count": 0, "dismiss_streak": 2},
        }

        event = _make_event(
            FeedbackSignal.INSIGHT_USEFUL,
            {"insight_type": "follow_up"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.recommendation_weights["follow_up"]["dismiss_streak"] == 0

    @pytest.mark.asyncio
    async def test_insight_ignored_decays_and_counts(self, setup):
        consumer, pref, repo = setup
        pref.recommendation_weights = {
            "tip": {"weight": 1.0, "shown_count": 0, "ignore_count": 0, "dismiss_streak": 0},
        }

        event = _make_event(
            FeedbackSignal.INSIGHT_IGNORED,
            {"insight_type": "tip"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        stats = pref.recommendation_weights["tip"]
        assert stats["weight"] == pytest.approx(1.0 * _IGNORED_MULTIPLIER, abs=0.01)
        assert stats["ignore_count"] == 1
        assert stats["shown_count"] == 1

    @pytest.mark.asyncio
    async def test_insight_ignored_auto_suppresses_after_threshold(self, setup):
        consumer, pref, repo = setup
        pref.recommendation_weights = {
            "tip": {
                "weight": 0.96,
                "shown_count": 2,
                "ignore_count": _IGNORE_SUPPRESS_THRESHOLD - 1,
                "dismiss_streak": 0,
            },
        }

        event = _make_event(
            FeedbackSignal.INSIGHT_IGNORED,
            {"insight_type": "tip"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert "tip" in repo.suppress_calls
        assert "tip" in pref.suppressed_types

    @pytest.mark.asyncio
    async def test_insight_never_again_permanently_suppresses(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.INSIGHT_NEVER_AGAIN,
            {"insight_type": "favor_reciprocation"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert "favor_reciprocation" in repo.suppress_calls
        assert "favor_reciprocation" in pref.suppressed_types

    @pytest.mark.asyncio
    async def test_suggestion_acted_boosts(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.SUGGESTION_ACTED,
            {"suggestion_type": "contact_reminder"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        stats = pref.recommendation_weights["contact_reminder"]
        assert stats["weight"] > _DEFAULT_WEIGHT
        assert stats["dismiss_streak"] == 0

    @pytest.mark.asyncio
    async def test_suggestion_dismissed_decays(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.SUGGESTION_DISMISSED,
            {"suggestion_type": "gift_reminder"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        stats = pref.recommendation_weights["gift_reminder"]
        assert stats["weight"] == pytest.approx(1.0 * _DISMISSED_MULTIPLIER, abs=0.01)
        assert stats["dismiss_streak"] == 1

    @pytest.mark.asyncio
    async def test_suggestion_dismissed_streak_suppresses(self, setup):
        consumer, pref, repo = setup
        pref.recommendation_weights = {
            "gift_reminder": {
                "weight": 0.64,
                "shown_count": 2,
                "ignore_count": 0,
                "dismiss_streak": _DISMISS_STREAK_THRESHOLD - 1,
            },
        }

        event = _make_event(
            FeedbackSignal.SUGGESTION_DISMISSED,
            {"suggestion_type": "gift_reminder"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert "gift_reminder" in repo.suppress_calls

    @pytest.mark.asyncio
    async def test_missing_insight_type_is_noop(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.INSIGHT_USEFUL,
            {},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert len(repo.update_calls) == 0

    @pytest.mark.asyncio
    async def test_handles_legacy_bare_float_weight(self, setup):
        """If recommendation_weights has a bare float instead of a stats dict,
        it should be treated gracefully."""
        consumer, pref, repo = setup
        pref.recommendation_weights = {"follow_up": 1.2}

        event = _make_event(
            FeedbackSignal.INSIGHT_USEFUL,
            {"insight_type": "follow_up"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        stats = pref.recommendation_weights["follow_up"]
        assert isinstance(stats, dict)
        assert stats["weight"] == pytest.approx(1.2 * _USEFUL_MULTIPLIER, abs=0.01)


# ---------------------------------------------------------------------------
# BufferTimeFeedbackConsumer tests
# ---------------------------------------------------------------------------

class TestBufferTimeFeedbackConsumer:

    @pytest.fixture()
    def setup(self):
        pref = FakeFamilyPreference()
        repo = FakeRepo(pref)
        db = _make_session_factory()
        consumer = BufferTimeFeedbackConsumer(db)
        consumer._get_repo = AsyncMock(return_value=repo)
        return consumer, pref, repo

    def test_protocol_conformance(self):
        db = _make_session_factory()
        consumer = BufferTimeFeedbackConsumer(db)
        assert isinstance(consumer, FeedbackConsumer)
        assert FeedbackSignal.BUFFER_ADJUSTED in consumer.consumes_signals

    @pytest.mark.asyncio
    async def test_ema_smoothing(self, setup):
        consumer, pref, repo = setup
        pref.buffer_minutes = {"meeting": 10}

        event = _make_event(
            FeedbackSignal.BUFFER_ADJUSTED,
            {"event_type": "meeting", "new_buffer_minutes": 30},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        # EMA: 0.3 * 30 + 0.7 * 10 = 9 + 7 = 16
        expected = round(_EMA_ALPHA * 30 + (1 - _EMA_ALPHA) * 10)
        assert pref.buffer_minutes["meeting"] == expected

    @pytest.mark.asyncio
    async def test_default_event_type(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.BUFFER_ADJUSTED,
            {"new_buffer_minutes": 20},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        # Uses "default" key when no event_type specified
        assert "default" in pref.buffer_minutes
        expected = round(_EMA_ALPHA * 20 + (1 - _EMA_ALPHA) * _DEFAULT_BUFFER)
        assert pref.buffer_minutes["default"] == expected

    @pytest.mark.asyncio
    async def test_new_event_type_uses_default_buffer(self, setup):
        consumer, pref, repo = setup
        pref.buffer_minutes = {}

        event = _make_event(
            FeedbackSignal.BUFFER_ADJUSTED,
            {"event_type": "location_change", "new_buffer_minutes": 60},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        expected = round(_EMA_ALPHA * 60 + (1 - _EMA_ALPHA) * _DEFAULT_BUFFER)
        assert pref.buffer_minutes["location_change"] == expected

    @pytest.mark.asyncio
    async def test_missing_new_buffer_is_noop(self, setup):
        consumer, pref, repo = setup

        event = _make_event(
            FeedbackSignal.BUFFER_ADJUSTED,
            {"event_type": "meeting"},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert len(repo.update_calls) == 0

    @pytest.mark.asyncio
    async def test_buffer_clamped_to_max(self, setup):
        consumer, pref, repo = setup
        pref.buffer_minutes = {"meeting": 170}

        event = _make_event(
            FeedbackSignal.BUFFER_ADJUSTED,
            {"event_type": "meeting", "new_buffer_minutes": 999},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.buffer_minutes["meeting"] <= 180

    @pytest.mark.asyncio
    async def test_buffer_clamped_to_min(self, setup):
        consumer, pref, repo = setup
        pref.buffer_minutes = {"meeting": 5}

        event = _make_event(
            FeedbackSignal.BUFFER_ADJUSTED,
            {"event_type": "meeting", "new_buffer_minutes": -10},
            family_id=pref.family_id,
        )
        await consumer.on_feedback(event)

        assert pref.buffer_minutes["meeting"] >= 0


# ---------------------------------------------------------------------------
# Integration: consumers with FeedbackBus
# ---------------------------------------------------------------------------

class TestConsumerBusIntegration:
    """Verify that consumers work correctly when registered with a FeedbackBus."""

    @pytest.fixture()
    def bus_and_consumers(self):
        bus = FeedbackBus()
        db = _make_session_factory()

        pref = FakeFamilyPreference()
        repo = FakeRepo(pref)

        priority = PriorityFeedbackConsumer(db)
        priority._get_repo = AsyncMock(return_value=repo)

        assoc = AssociationFeedbackConsumer(db)
        assoc._get_repo = AsyncMock(return_value=repo)

        rec = RecommendationFeedbackConsumer(db)
        rec._get_repo = AsyncMock(return_value=repo)

        buf = BufferTimeFeedbackConsumer(db)
        buf._get_repo = AsyncMock(return_value=repo)

        bus.register(priority)
        bus.register(assoc)
        bus.register(rec)
        bus.register(buf)

        return bus, pref, repo

    @pytest.mark.asyncio
    async def test_emit_routes_to_correct_consumer(self, bus_and_consumers):
        bus, pref, repo = bus_and_consumers

        await bus.emit(
            signal=FeedbackSignal.EVENT_CANCELLED,
            data={"event_type": "meeting"},
            family_id=pref.family_id,
            user_id=uuid4(),
        )

        # Should have written to event_type_severity, not others
        assert len(repo.update_calls) == 1
        field, _ = repo.update_calls[0]
        assert field == "event_type_severity"

    @pytest.mark.asyncio
    async def test_emit_insight_useful_routes_to_recommendation(self, bus_and_consumers):
        bus, pref, repo = bus_and_consumers

        await bus.emit(
            signal=FeedbackSignal.INSIGHT_USEFUL,
            data={"insight_type": "follow_up"},
            family_id=pref.family_id,
            user_id=uuid4(),
        )

        assert len(repo.update_calls) == 1
        field, _ = repo.update_calls[0]
        assert field == "recommendation_weights"

    @pytest.mark.asyncio
    async def test_emit_buffer_routes_to_buffer_consumer(self, bus_and_consumers):
        bus, pref, repo = bus_and_consumers

        await bus.emit(
            signal=FeedbackSignal.BUFFER_ADJUSTED,
            data={"event_type": "meeting", "new_buffer_minutes": 25},
            family_id=pref.family_id,
            user_id=uuid4(),
        )

        assert len(repo.update_calls) == 1
        field, _ = repo.update_calls[0]
        assert field == "buffer_minutes"

    @pytest.mark.asyncio
    async def test_all_signals_have_at_least_one_consumer(self, bus_and_consumers):
        bus, _, _ = bus_and_consumers
        for signal in FeedbackSignal:
            assert bus.get_consumer_count(signal) >= 1, (
                f"No consumer registered for {signal.value}"
            )


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestConsumerErrorHandling:

    @pytest.mark.asyncio
    async def test_consumer_error_does_not_propagate(self):
        """Consumer on_feedback catches internal errors gracefully."""
        db = _make_session_factory()
        consumer = PriorityFeedbackConsumer(db)
        # Make _get_repo raise
        consumer._get_repo = AsyncMock(side_effect=RuntimeError("db connection lost"))

        event = _make_event(
            FeedbackSignal.EVENT_CANCELLED,
            {"event_type": "meeting"},
        )
        # Should not raise
        await consumer.on_feedback(event)
