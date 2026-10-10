"""Unit tests for Insight Engine v2 modules.

Covers:
- InformationTriage (tier classification)
- RuleEngineInsights (deadline + admin reminders)
- DynamicPriorityAdjuster (query-time scoring)
- DeliveryTimingEngine (wave selection + scoring)
- PrepChainEngine (preparation step generation)
"""

import dataclasses
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.modules.insight.models import (
    EntitySpec,
    GenerationLevel,
    InformationTier,
    InsightCandidate,
    InsightType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(**overrides) -> InsightCandidate:
    """Create a minimal InsightCandidate with defaults."""
    defaults = {
        "insight_type": InsightType.TIME.value,
        "title": "Test",
        "content": "Test content",
        "importance": 50,
        "urgency": 50,
    }
    defaults.update(overrides)
    return InsightCandidate(**defaults)


# ===========================================================================
# InformationTriage
# ===========================================================================


class TestInformationTriage:
    """Tests for information_triage.InformationTriage."""

    @pytest.fixture
    def triage(self):
        from src.modules.insight.information_triage import InformationTriage
        return InformationTriage()

    def test_l0_auto_resolvable(self, triage):
        c = _make_candidate(source_context={"auto_resolvable": True})
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L0_AUTO.value

    def test_l0_positive_low_urgency(self, triage):
        c = _make_candidate(
            insight_type=InsightType.POSITIVE_AFFIRMATION.value,
            urgency=20,
        )
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L0_AUTO.value

    def test_l0_confirmed_booking(self, triage):
        c = _make_candidate(source_context={"confirmed_booking": True})
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L0_AUTO.value

    def test_l1_low_urgency_low_importance(self, triage):
        c = _make_candidate(importance=30, urgency=20)
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L1_PASSIVE.value

    def test_l1_weather_low_importance(self, triage):
        c = _make_candidate(
            insight_type=InsightType.WEATHER_CARE.value,
            importance=40,
            urgency=50,
        )
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L1_PASSIVE.value

    def test_l1_trend_alert_below_threshold(self, triage):
        c = _make_candidate(
            insight_type=InsightType.TREND_ALERT.value,
            importance=45,
            urgency=40,
        )
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L1_PASSIVE.value

    def test_l2_high_importance_urgency(self, triage):
        c = _make_candidate(importance=80, urgency=80)
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L2_FORMAL.value

    def test_l2_medium_urgency(self, triage):
        c = _make_candidate(importance=60, urgency=60)
        result = triage.classify(c)
        assert result.information_tier == InformationTier.L2_FORMAL.value

    def test_classify_batch_returns_new_list(self, triage):
        candidates = [_make_candidate(importance=10, urgency=10)]
        result = triage.classify_batch(candidates)
        assert len(result) == 1
        assert result[0] is not candidates[0]
        assert result[0].information_tier is not None

    def test_immutability(self, triage):
        """Classify must return a new object, not mutate the original."""
        c = _make_candidate(importance=10, urgency=10)  # L1_PASSIVE tier
        original_tier = c.information_tier
        result = triage.classify(c)
        # Original should still have default tier
        assert c.information_tier == original_tier
        # Result should be L1_PASSIVE (low importance+urgency)
        assert result.information_tier == InformationTier.L1_PASSIVE.value
        # Different objects
        assert result is not c


# ===========================================================================
# RuleEngineInsights (non-DB parts)
# ===========================================================================


class TestRuleEngineDeadlineReminders:
    """Tests for RuleEngineInsights._deadline_reminders (pure logic)."""

    @pytest.fixture
    def engine(self):
        from src.modules.insight.rule_engine_insights import RuleEngineInsights
        return RuleEngineInsights()

    def _make_signals(self, protected):
        """Build a minimal AllSignals-like object."""
        from src.modules.insight.insight_signal_collector import AllSignals
        return AllSignals(protected=protected)

    def test_deadline_within_3_days(self, engine):
        deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        signals = self._make_signals([{
            "signal_type": "commitment",
            "deadline": deadline,
            "commitment_id": str(uuid4()),
            "who": "Alice",
            "what": "买礼物",
            "to_whom": "Bob",
        }])
        result = engine._deadline_reminders(signals)
        assert len(result) == 1
        assert result[0].generation_level == GenerationLevel.L1_RULE.value
        assert "买礼物" in result[0].title

    def test_deadline_beyond_3_days_skipped(self, engine):
        deadline = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        signals = self._make_signals([{
            "signal_type": "commitment",
            "deadline": deadline,
            "commitment_id": str(uuid4()),
            "who": "Alice",
            "what": "远期任务",
        }])
        result = engine._deadline_reminders(signals)
        assert len(result) == 0

    def test_non_commitment_signals_ignored(self, engine):
        signals = self._make_signals([{
            "signal_type": "favor",
            "deadline": datetime.now(timezone.utc).isoformat(),
        }])
        result = engine._deadline_reminders(signals)
        assert len(result) == 0

    def test_missing_deadline_skipped(self, engine):
        signals = self._make_signals([{
            "signal_type": "commitment",
            "who": "Alice",
            "what": "no deadline",
        }])
        result = engine._deadline_reminders(signals)
        assert len(result) == 0


class TestRuleEnginePeriodicAdmin:
    """Tests for RuleEngineInsights._periodic_admin_reminders."""

    @pytest.fixture
    def engine(self):
        from src.modules.insight.rule_engine_insights import RuleEngineInsights
        return RuleEngineInsights()

    def _make_signals(self, events):
        from src.modules.insight.insight_signal_collector import AllSignals
        return AllSignals(events=events)

    def test_bill_payment_within_14_days(self, engine):
        start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        signals = self._make_signals([{
            "event_type": "bill_payment",
            "start": start,
            "event_id": str(uuid4()),
            "title": "水费缴纳",
        }])
        result = engine._periodic_admin_reminders(signals)
        assert len(result) == 1
        assert result[0].insight_type == InsightType.LIFE_ADMIN.value
        assert "水费" in result[0].title

    def test_non_admin_event_type_skipped(self, engine):
        start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        signals = self._make_signals([{
            "event_type": "family_gathering",
            "start": start,
            "title": "家庭聚会",
        }])
        result = engine._periodic_admin_reminders(signals)
        assert len(result) == 0

    def test_event_beyond_14_days_skipped(self, engine):
        start = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        signals = self._make_signals([{
            "event_type": "medical_check",
            "start": start,
            "title": "体检",
        }])
        result = engine._periodic_admin_reminders(signals)
        assert len(result) == 0


# ===========================================================================
# DynamicPriorityAdjuster
# ===========================================================================


class TestDynamicPriorityAdjuster:
    """Tests for dynamic_priority.DynamicPriorityAdjuster."""

    @pytest.fixture
    def adjuster(self):
        from src.modules.insight.dynamic_priority import DynamicPriorityAdjuster
        return DynamicPriorityAdjuster()

    @pytest.fixture
    def default_context(self):
        from src.modules.insight.dynamic_priority import UserQueryContext
        return UserQueryContext()

    def _make_insight(self, **kwargs):
        """Create a mock Insight-like object for adjust()."""

        class FakeInsight:
            def __init__(self, **kw):
                self.importance = kw.get("importance", 50)
                self.urgency = kw.get("urgency", 50)
                self.insight_type = kw.get("insight_type", "time")
                self.information_tier = kw.get("information_tier", "L2_FORMAL")
                self.expires_at = kw.get("expires_at")
                self.entities = kw.get("entities", [])

        return FakeInsight(**kwargs)

    def test_default_context_no_change(self, adjuster, default_context):
        insight = self._make_insight(importance=50, urgency=50)
        imp, urg = adjuster.adjust(insight, default_context)
        assert imp == 50
        assert urg == 50

    def test_entity_interaction_boosts_urgency(self, adjuster):
        from src.modules.insight.dynamic_priority import UserQueryContext

        class FakeEntity:
            def __init__(self, eid):
                self.entity_id = eid

        entity_id = str(uuid4())
        insight = self._make_insight(urgency=50, entities=[FakeEntity(entity_id)])
        ctx = UserQueryContext(recent_entity_ids=frozenset({entity_id}))
        imp, urg = adjuster.adjust(insight, ctx)
        assert urg == 70  # +20

    def test_dismissal_penalty(self, adjuster):
        from src.modules.insight.dynamic_priority import UserQueryContext

        insight = self._make_insight(insight_type="time", importance=60)
        ctx = UserQueryContext(dismiss_count_7d={"time": 5})
        imp, urg = adjuster.adjust(insight, ctx)
        assert imp == 30  # -30

    def test_deadline_urgency_force(self, adjuster, default_context):
        expires = datetime.now(timezone.utc) + timedelta(hours=12)
        insight = self._make_insight(urgency=40, expires_at=expires)
        imp, urg = adjuster.adjust(insight, default_context)
        assert urg == 95  # forced to floor

    def test_high_density_non_formal_penalty(self, adjuster):
        from src.modules.insight.dynamic_priority import UserQueryContext

        insight = self._make_insight(
            importance=60,
            information_tier="L1_PASSIVE",
        )
        ctx = UserQueryContext(density_score=0.9)
        imp, urg = adjuster.adjust(insight, ctx)
        assert imp == 45  # -15

    def test_weekend_family_boost(self, adjuster):
        from src.modules.insight.dynamic_priority import UserQueryContext

        insight = self._make_insight(
            importance=60,
            insight_type="relationship",
        )
        ctx = UserQueryContext(is_weekend=True)
        imp, urg = adjuster.adjust(insight, ctx)
        assert imp == 70  # +10

    def test_low_mood_suppresses_negative(self, adjuster):
        from src.modules.insight.dynamic_priority import UserQueryContext

        insight = self._make_insight(
            importance=60,
            urgency=50,
            insight_type="trend_alert",
        )
        ctx = UserQueryContext(user_mood="low")
        imp, urg = adjuster.adjust(insight, ctx)
        assert imp == 40  # -20

    def test_clamped_to_0_100(self, adjuster):
        from src.modules.insight.dynamic_priority import UserQueryContext

        # Low importance + dismissal + density should clamp to 0
        insight = self._make_insight(
            importance=10,
            insight_type="trend_alert",
            information_tier="L1_PASSIVE",
        )
        ctx = UserQueryContext(
            dismiss_count_7d={"trend_alert": 5},
            density_score=0.9,
            user_mood="low",
        )
        imp, urg = adjuster.adjust(insight, ctx)
        assert imp >= 0
        assert urg >= 0


# ===========================================================================
# DeliveryTimingEngine
# ===========================================================================


class TestDeliveryTimingEngine:
    """Tests for delivery_timing_engine.DeliveryTimingEngine."""

    @pytest.fixture
    def engine(self):
        from src.modules.insight.delivery_timing_engine import DeliveryTimingEngine
        return DeliveryTimingEngine()

    def test_get_wave_config_defaults(self, engine):
        wave = engine.get_wave_config("morning")
        assert wave.name == "morning"
        assert wave.hour == 7
        assert wave.max_items == 3
        assert "weather_care" in wave.focus_types

    def test_get_wave_config_with_overrides(self, engine):
        overrides = {"morning": {"hour": 8, "max_items": 5}}
        wave = engine.get_wave_config("morning", overrides)
        assert wave.hour == 8
        assert wave.max_items == 5
        assert wave.style == "quick"  # not user-configurable

    def test_unknown_wave_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown wave"):
            engine.get_wave_config("midnight")

    def test_is_wave_enabled_default_true(self, engine):
        assert engine.is_wave_enabled("noon") is True

    def test_is_wave_disabled(self, engine):
        waves = {"noon": {"enabled": False}}
        assert engine.is_wave_enabled("noon", waves) is False

    def test_select_for_wave_respects_max_items(self, engine):
        from src.modules.insight.delivery_timing_engine import (
            DeliveryWave,
            UserMomentState,
        )

        wave = DeliveryWave(
            name="test", hour=7, max_items=2,
            focus_types=("time",), style="quick",
        )
        moment = UserMomentState()

        insights = [self._make_fake_insight(i) for i in range(5)]
        selected = engine.select_for_wave(insights, wave, moment)
        assert len(selected) <= 2

    def test_select_for_wave_filters_l0_auto(self, engine):
        from src.modules.insight.delivery_timing_engine import (
            DeliveryWave,
            UserMomentState,
        )

        wave = DeliveryWave(
            name="test", hour=7, max_items=5,
            focus_types=("time",), style="quick",
        )
        moment = UserMomentState()

        insights = [
            self._make_fake_insight(1, information_tier="L0_AUTO"),
            self._make_fake_insight(2, information_tier="L2_FORMAL"),
        ]
        selected = engine.select_for_wave(insights, wave, moment)
        assert len(selected) == 1

    def test_compute_daily_budget_new_user(self, engine):
        assert engine.compute_daily_budget(3, 0.0) == 3

    def test_compute_daily_budget_disengaged(self, engine):
        assert engine.compute_daily_budget(30, 0.6) == 1

    def test_compute_daily_budget_active(self, engine):
        assert engine.compute_daily_budget(30, 0.1) == 10

    def test_focus_type_bonus(self, engine):
        """Insights matching wave focus types should score higher."""
        from src.modules.insight.delivery_timing_engine import (
            DeliveryWave,
            UserMomentState,
        )

        wave = DeliveryWave(
            name="test", hour=7, max_items=5,
            focus_types=("weather_care",), style="quick",
        )
        moment = UserMomentState()

        focus_insight = self._make_fake_insight(1, insight_type="weather_care", importance=50)
        other_insight = self._make_fake_insight(2, insight_type="relationship", importance=50)

        focus_score = engine._compute_delivery_score(focus_insight, wave, moment)
        other_score = engine._compute_delivery_score(other_insight, wave, moment)
        assert focus_score > other_score

    @staticmethod
    def _make_fake_insight(idx, **overrides):
        class FakeInsight:
            def __init__(self, **kw):
                self.id = uuid4()
                self.importance = kw.get("importance", 60)
                self.urgency = kw.get("urgency", 60)
                self.insight_type = kw.get("insight_type", "time")
                self.information_tier = kw.get("information_tier", "L2_FORMAL")

        return FakeInsight(**overrides)


# ===========================================================================
# PrepChainEngine
# ===========================================================================


class TestPrepChainEngine:
    """Tests for prep_chain_engine.PrepChainEngine."""

    @pytest.fixture
    def engine(self):
        from src.modules.insight.prep_chain_engine import PrepChainEngine
        return PrepChainEngine()

    def test_travel_event_generates_candidates(self, engine):
        event_date = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        # Target date = 3 days before event -> should match "预订确认" step
        target = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)

        events = [{
            "event_type": "travel",
            "normalized_start": event_date.isoformat(),
            "event_id": str(uuid4()),
            "title": "北京出差",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 1
        assert "预订确认" in result[0].title
        assert result[0].insight_type == "prep_chain"
        assert result[0].generation_level == GenerationLevel.L1_RULE.value

    def test_important_date_on_day(self, engine):
        event_date = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)

        events = [{
            "is_important_date": True,
            "normalized_start": event_date.isoformat(),
            "event_id": str(uuid4()),
            "title": "妈妈生日",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 1
        assert "发送祝福" in result[0].title

    def test_commitment_deadline_today(self, engine):
        event_date = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)

        events = [{
            "is_commitment_deadline": True,
            "normalized_start": event_date.isoformat(),
            "event_id": str(uuid4()),
            "title": "交报告",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 1
        assert "到期提醒" in result[0].title

    def test_unmatched_event_type_skipped(self, engine):
        event_date = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)

        events = [{
            "event_type": "personal_note",
            "normalized_start": event_date.isoformat(),
            "title": "随便写写",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 0

    def test_no_match_date_skipped(self, engine):
        event_date = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        # Target date doesn't match any step
        target = datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc)

        events = [{
            "event_type": "travel",
            "normalized_start": event_date.isoformat(),
            "event_id": str(uuid4()),
            "title": "北京出差",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 0

    def test_action_options_present(self, engine):
        event_date = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)

        events = [{
            "is_important_date": True,
            "normalized_start": event_date.isoformat(),
            "event_id": str(uuid4()),
            "title": "纪念日",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 1
        assert result[0].action_options is not None
        assert len(result[0].action_options) == 3

    def test_entities_include_event_and_trip(self, engine):
        event_date = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)

        event_id = str(uuid4())
        trip_id = str(uuid4())
        events = [{
            "event_type": "travel",
            "normalized_start": event_date.isoformat(),
            "event_id": event_id,
            "trip_id": trip_id,
            "title": "Trip",
        }]
        result = engine.generate_for_date(target, events)
        assert len(result) == 1
        entity_types = {e.entity_type for e in result[0].entities}
        assert "event" in entity_types
        assert "trip" in entity_types


# ===========================================================================
# build_moment_state
# ===========================================================================


class TestBuildMomentState:
    """Tests for delivery_timing_engine.build_moment_state."""

    def test_morning_high_energy(self):
        from src.modules.insight.delivery_timing_engine import build_moment_state
        state = build_moment_state(current_hour=8)
        assert state.energy_level == "high"

    def test_high_density_busy(self):
        from src.modules.insight.delivery_timing_engine import build_moment_state
        state = build_moment_state(density_score=0.9, current_hour=10)
        assert state.receptivity == "busy"

    def test_many_unreads_busy(self):
        from src.modules.insight.delivery_timing_engine import build_moment_state
        state = build_moment_state(unread_insight_count=6, current_hour=10)
        assert state.receptivity == "busy"

    def test_low_density_open(self):
        from src.modules.insight.delivery_timing_engine import build_moment_state
        state = build_moment_state(density_score=0.1, current_hour=10)
        assert state.receptivity == "open"


# ===========================================================================
# InsightCard DTO (new fields)
# ===========================================================================


class TestInsightCardNewFields:
    """Verify InsightCard DTO includes new v2 fields."""

    def test_new_fields_present(self):
        from src.modules.insight.insight_query_service import InsightCard
        card = InsightCard(
            id=uuid4(),
            insight_type="time",
            title="Test",
            content="Content",
            importance=50,
            urgency=50,
            status="pending",
            context_hint="因为明天有会",
            best_action_window="今天下午",
            information_tier="L2_FORMAL",
            generation_level="L1",
            created_at=datetime.now(timezone.utc),
        )
        assert card.context_hint == "因为明天有会"
        assert card.best_action_window == "今天下午"
        assert card.information_tier == "L2_FORMAL"
        assert card.generation_level == "L1"

    def test_new_fields_optional(self):
        from src.modules.insight.insight_query_service import InsightCard
        card = InsightCard(
            id=uuid4(),
            insight_type="time",
            title="Test",
            content="Content",
            importance=50,
            urgency=50,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        assert card.context_hint is None
        assert card.best_action_window is None
        assert card.information_tier is None
        assert card.generation_level is None
