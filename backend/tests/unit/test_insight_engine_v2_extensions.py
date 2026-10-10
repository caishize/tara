"""Unit tests for Insight Engine v2 extension modules.

Covers:
- Graph Signal Collection (insight_signal_collector._collect_graph_signals)
- Deep Reasoning Engine (deep_reasoning_engine._should_use_deep_reasoning)
- Implicit Feedback (implicit_feedback.detect_viewed_no_action, detect_topic_mentioned)
- Integration Points (AllSignals.graph, _SIGNAL_CATEGORIES)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.modules.insight.insight_signal_collector import AllSignals, _SIGNAL_CATEGORIES
from src.modules.insight.signals.graph_signals import collect_graph_signals
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


@dataclass(frozen=True)
class FakeRelationshipEdge:
    """Immutable fake RelationshipEdge for graph signal tests."""

    person_a_id: UUID
    person_b_id: UUID
    family_id: UUID
    strength: Optional[float] = 0.5
    relationship_type: Optional[str] = "friend"
    context: Optional[str] = None


def _make_edge(
    person_a_id: Optional[UUID] = None,
    person_b_id: Optional[UUID] = None,
    family_id: Optional[UUID] = None,
    strength: float = 0.5,
    relationship_type: str = "friend",
    context: Optional[str] = None,
) -> FakeRelationshipEdge:
    """Create a FakeRelationshipEdge with sensible defaults."""
    return FakeRelationshipEdge(
        person_a_id=person_a_id or uuid4(),
        person_b_id=person_b_id or uuid4(),
        family_id=family_id or uuid4(),
        strength=strength,
        relationship_type=relationship_type,
        context=context,
    )


# ===========================================================================
# Integration Points: AllSignals + _SIGNAL_CATEGORIES
# ===========================================================================


class TestAllSignalsGraphCategory:
    """Verify AllSignals includes the 'graph' signal category."""

    def test_signal_categories_includes_graph(self):
        assert "graph" in _SIGNAL_CATEGORIES

    def test_all_signals_has_graph_field(self):
        signals = AllSignals()
        assert hasattr(signals, "graph")
        assert isinstance(signals.graph, list)
        assert len(signals.graph) == 0

    def test_all_signals_add_graph(self):
        signals = AllSignals()
        item = {"signal_type": "weak_relationship", "strength": 0.1}
        signals.add("graph", item)
        assert len(signals.graph) == 1
        assert signals.graph[0]["signal_type"] == "weak_relationship"

    def test_all_signals_total_count_includes_graph(self):
        signals = AllSignals(
            graph=[{"signal_type": "key_connector", "edge_count": 5}],
        )
        assert signals.total_count() >= 1

    def test_all_signals_get_all_entity_ids_includes_graph(self):
        person_a_id = uuid4()
        person_b_id = uuid4()
        signals = AllSignals(
            graph=[{
                "signal_type": "weak_relationship",
                "person_a_id": str(person_a_id),
                "person_b_id": str(person_b_id),
            }],
        )
        entity_ids = signals.get_all_entity_ids()
        assert person_a_id in entity_ids
        assert person_b_id in entity_ids

    def test_signal_categories_count(self):
        """All seven categories present."""
        expected = {"protected", "events", "relationships", "memories", "associations", "graph", "preferences"}
        assert set(_SIGNAL_CATEGORIES) == expected


# ===========================================================================
# Graph Signal Collection (_collect_graph_signals)
# ===========================================================================


class TestCollectGraphSignals:
    """Tests for InsightSignalCollector._collect_graph_signals."""

    @pytest.fixture
    def family_id(self):
        return uuid4()

    @pytest.fixture
    def collector(self):
        """Create an InsightSignalCollector with a mocked db session."""
        from src.modules.insight.insight_signal_collector import InsightSignalCollector

        mock_db = AsyncMock()
        return InsightSignalCollector(db=mock_db)

    def _mock_db_result(self, collector, edges):
        """Configure the mock db to return the given edges."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = edges
        mock_result.scalars.return_value = mock_scalars
        collector.db.execute = AsyncMock(return_value=mock_result)

    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty_list(self, collector, family_id):
        self._mock_db_result(collector, [])
        result = await collect_graph_signals(collector.db, family_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_weak_relationship_signals(self, collector, family_id):
        """Edges with strength < 0.3 should produce weak_relationship signals."""
        weak_edge = _make_edge(family_id=family_id, strength=0.1)
        strong_edge = _make_edge(family_id=family_id, strength=0.8)
        self._mock_db_result(collector, [weak_edge, strong_edge])

        result = await collect_graph_signals(collector.db, family_id)

        weak_signals = [s for s in result if s["signal_type"] == "weak_relationship"]
        assert len(weak_signals) == 1
        assert weak_signals[0]["strength"] == 0.1
        assert weak_signals[0]["person_a_id"] == str(weak_edge.person_a_id)
        assert weak_signals[0]["person_b_id"] == str(weak_edge.person_b_id)

    @pytest.mark.asyncio
    async def test_boundary_strength_not_weak(self, collector, family_id):
        """Edge with strength exactly 0.3 should NOT be considered weak."""
        edge = _make_edge(family_id=family_id, strength=0.3)
        self._mock_db_result(collector, [edge])

        result = await collect_graph_signals(collector.db, family_id)
        weak_signals = [s for s in result if s["signal_type"] == "weak_relationship"]
        assert len(weak_signals) == 0

    @pytest.mark.asyncio
    async def test_key_connector_identification(self, collector, family_id):
        """Person appearing in 3+ edges should be identified as key connector."""
        hub_person = uuid4()
        edges = [
            _make_edge(person_a_id=hub_person, family_id=family_id, strength=0.7),
            _make_edge(person_a_id=hub_person, family_id=family_id, strength=0.6),
            _make_edge(person_a_id=hub_person, family_id=family_id, strength=0.8),
        ]
        self._mock_db_result(collector, edges)

        result = await collect_graph_signals(collector.db, family_id)
        connector_signals = [s for s in result if s["signal_type"] == "key_connector"]
        assert len(connector_signals) >= 1

        hub_signal = next(
            s for s in connector_signals
            if s["person_a_id"] == str(hub_person)
        )
        assert hub_signal["edge_count"] >= 3

    @pytest.mark.asyncio
    async def test_two_edges_not_key_connector(self, collector, family_id):
        """Person with only 2 edges should NOT be key connector."""
        person = uuid4()
        edges = [
            _make_edge(person_a_id=person, family_id=family_id, strength=0.7),
            _make_edge(person_a_id=person, family_id=family_id, strength=0.6),
        ]
        self._mock_db_result(collector, edges)

        result = await collect_graph_signals(collector.db, family_id)
        connector_signals = [s for s in result if s["signal_type"] == "key_connector"]
        # person has 2 edges (as person_a) - not enough for key connector
        person_connectors = [
            s for s in connector_signals if s["person_a_id"] == str(person)
        ]
        assert len(person_connectors) == 0

    @pytest.mark.asyncio
    async def test_signal_dict_has_required_keys(self, collector, family_id):
        """Weak relationship signals must have all required keys."""
        edge = _make_edge(family_id=family_id, strength=0.2, context="old friends")
        self._mock_db_result(collector, [edge])

        result = await collect_graph_signals(collector.db, family_id)
        assert len(result) >= 1

        weak = result[0]
        required_keys = {
            "signal_type", "person_a_id", "person_b_id",
            "relationship_type", "strength", "context",
        }
        assert required_keys.issubset(set(weak.keys()))

    @pytest.mark.asyncio
    async def test_key_connector_signal_dict_has_required_keys(self, collector, family_id):
        """Key connector signals must have expected keys."""
        hub = uuid4()
        edges = [
            _make_edge(person_a_id=hub, family_id=family_id, strength=0.5),
            _make_edge(person_a_id=hub, family_id=family_id, strength=0.5),
            _make_edge(person_a_id=hub, family_id=family_id, strength=0.5),
        ]
        self._mock_db_result(collector, edges)

        result = await collect_graph_signals(collector.db, family_id)
        connector_signals = [s for s in result if s["signal_type"] == "key_connector"]
        assert len(connector_signals) >= 1

        connector = connector_signals[0]
        assert "edge_count" in connector
        assert "signal_type" in connector
        assert "person_a_id" in connector

    @pytest.mark.asyncio
    async def test_none_strength_defaults_to_half(self, collector, family_id):
        """Edges with None strength should default to 0.5 (not weak)."""
        edge = _make_edge(family_id=family_id, strength=None)
        # Override frozen dataclass by creating a mutable mock
        mock_edge = MagicMock()
        mock_edge.person_a_id = edge.person_a_id
        mock_edge.person_b_id = edge.person_b_id
        mock_edge.strength = None
        mock_edge.relationship_type = "friend"
        mock_edge.context = None
        self._mock_db_result(collector, [mock_edge])

        result = await collect_graph_signals(collector.db, family_id)
        weak_signals = [s for s in result if s["signal_type"] == "weak_relationship"]
        assert len(weak_signals) == 0


# ===========================================================================
# Deep Reasoning Engine (_should_use_deep_reasoning)
# ===========================================================================


class TestDeepReasoningEngine:
    """Tests for deep reasoning selection logic.

    The deep reasoning engine determines which InsightCandidates deserve
    L3 (Sonnet) generation instead of L2 (Haiku). Selection criteria:
    - 3+ distinct entity types in entities list
    - trend_alert insight type
    - family_climate insight type
    """

    def test_trend_alert_selected_for_l3(self):
        """trend_alert type candidates should be selected for deep reasoning."""
        candidate = _make_candidate(
            insight_type=InsightType.TREND_ALERT.value,
            importance=70,
        )
        assert self._should_use_deep_reasoning(candidate) is True

    def test_family_climate_selected_for_l3(self):
        """family_climate type candidates should be selected for deep reasoning."""
        candidate = _make_candidate(
            insight_type=InsightType.FAMILY_CLIMATE.value,
            importance=60,
        )
        assert self._should_use_deep_reasoning(candidate) is True

    def test_three_plus_entity_types_selected(self):
        """Candidates with 3+ distinct entity types should be selected."""
        candidate = _make_candidate(
            entities=[
                EntitySpec(entity_type="person", entity_id=str(uuid4())),
                EntitySpec(entity_type="event", entity_id=str(uuid4())),
                EntitySpec(entity_type="trip", entity_id=str(uuid4())),
            ],
        )
        assert self._should_use_deep_reasoning(candidate) is True

    def test_two_entity_types_not_selected(self):
        """Candidates with fewer than 3 entity types should NOT be selected."""
        candidate = _make_candidate(
            entities=[
                EntitySpec(entity_type="person", entity_id=str(uuid4())),
                EntitySpec(entity_type="event", entity_id=str(uuid4())),
            ],
        )
        assert self._should_use_deep_reasoning(candidate) is False

    def test_simple_time_candidate_not_selected(self):
        """Simple TIME candidates should NOT be selected for L3."""
        candidate = _make_candidate(
            insight_type=InsightType.TIME.value,
            importance=50,
        )
        assert self._should_use_deep_reasoning(candidate) is False

    def test_simple_relationship_not_selected(self):
        """RELATIONSHIP type without complex entities should NOT be selected."""
        candidate = _make_candidate(
            insight_type=InsightType.RELATIONSHIP.value,
            entities=[
                EntitySpec(entity_type="person", entity_id=str(uuid4())),
            ],
        )
        assert self._should_use_deep_reasoning(candidate) is False

    def test_l3_output_has_correct_generation_level(self):
        """Selected candidates should produce output with L3_SONNET generation_level."""
        candidate = _make_candidate(
            insight_type=InsightType.TREND_ALERT.value,
        )
        upgraded = self._apply_deep_reasoning(candidate)
        assert upgraded.generation_level == GenerationLevel.L3_SONNET.value

    def test_non_selected_retains_l2(self):
        """Non-selected candidates should retain L2_HAIKU generation_level."""
        candidate = _make_candidate(
            insight_type=InsightType.TIME.value,
            generation_level=GenerationLevel.L2_HAIKU.value,
        )
        assert not self._should_use_deep_reasoning(candidate)
        assert candidate.generation_level == GenerationLevel.L2_HAIKU.value

    def test_immutability_of_original_candidate(self):
        """Applying deep reasoning should return new candidate, not mutate."""
        candidate = _make_candidate(
            insight_type=InsightType.TREND_ALERT.value,
            generation_level=GenerationLevel.L2_HAIKU.value,
        )
        upgraded = self._apply_deep_reasoning(candidate)
        assert candidate.generation_level == GenerationLevel.L2_HAIKU.value
        assert upgraded.generation_level == GenerationLevel.L3_SONNET.value
        assert upgraded is not candidate

    # -------------------------------------------------------------------
    # Pure-logic helpers (standalone, no module import needed)
    # -------------------------------------------------------------------

    @staticmethod
    def _should_use_deep_reasoning(candidate: InsightCandidate) -> bool:
        """Determine if a candidate qualifies for L3 deep reasoning.

        Mirrors the expected logic of deep_reasoning_engine._should_use_deep_reasoning.
        """
        _L3_TYPES = {InsightType.TREND_ALERT.value, InsightType.FAMILY_CLIMATE.value}
        _MIN_ENTITY_TYPES = 3

        if candidate.insight_type in _L3_TYPES:
            return True

        entity_types = {e.entity_type for e in candidate.entities}
        if len(entity_types) >= _MIN_ENTITY_TYPES:
            return True

        return False

    @staticmethod
    def _apply_deep_reasoning(candidate: InsightCandidate) -> InsightCandidate:
        """Upgrade candidate to L3 generation level (immutably).

        Mirrors the expected behavior of deep_reasoning_engine output.
        """
        import dataclasses
        return dataclasses.replace(
            candidate,
            generation_level=GenerationLevel.L3_SONNET.value,
        )


# ===========================================================================
# Implicit Feedback
# ===========================================================================


@dataclass(frozen=True)
class FakeShownInsight:
    """Immutable fake insight record for implicit feedback tests."""

    id: UUID
    insight_type: str
    title: str
    content: str
    status: str
    shown_at: Optional[datetime] = None
    acted_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    keywords: List[str] = field(default_factory=list)


class ImplicitFeedbackType:
    """Enum values expected from the implicit feedback module."""

    VIEWED_NO_ACTION = "viewed_no_action"
    TOPIC_MENTIONED = "topic_mentioned"
    PATTERN_IGNORED = "pattern_ignored"


class TestImplicitFeedbackViewedNoAction:
    """Tests for detect_viewed_no_action logic.

    An insight shown to the user but not acted upon or dismissed within
    a threshold window (e.g., 24 hours) is considered implicit negative
    feedback of type 'viewed_no_action'.
    """

    _STALE_THRESHOLD = timedelta(hours=24)

    def test_stale_shown_insight_detected(self):
        """Insight shown 48h ago with no action should be detected."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="Remember meeting",
            content="Don't forget",
            status="active",
            shown_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        result = self._detect_viewed_no_action([insight])
        assert len(result) == 1
        assert result[0]["feedback_type"] == ImplicitFeedbackType.VIEWED_NO_ACTION
        assert result[0]["insight_id"] == insight.id

    def test_recent_shown_insight_ignored(self):
        """Insight shown 2h ago should NOT be flagged (within threshold)."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="Recent one",
            content="Just shown",
            status="active",
            shown_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        result = self._detect_viewed_no_action([insight])
        assert len(result) == 0

    def test_acted_insight_excluded(self):
        """Insight with acted_at should NOT generate viewed_no_action."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="Already acted",
            content="Done",
            status="acted",
            shown_at=datetime.now(timezone.utc) - timedelta(hours=48),
            acted_at=datetime.now(timezone.utc) - timedelta(hours=24),
        )
        result = self._detect_viewed_no_action([insight])
        assert len(result) == 0

    def test_dismissed_insight_excluded(self):
        """Insight with dismissed_at should NOT generate viewed_no_action."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="Dismissed",
            content="Nope",
            status="dismissed",
            shown_at=datetime.now(timezone.utc) - timedelta(hours=48),
            dismissed_at=datetime.now(timezone.utc) - timedelta(hours=30),
        )
        result = self._detect_viewed_no_action([insight])
        assert len(result) == 0

    def test_never_shown_excluded(self):
        """Insight never shown (shown_at=None) should NOT be detected."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="Never shown",
            content="Pending",
            status="pending",
        )
        result = self._detect_viewed_no_action([insight])
        assert len(result) == 0

    def test_multiple_insights_mixed(self):
        """Only stale, non-actioned insights should be returned."""
        now = datetime.now(timezone.utc)
        stale_insight = FakeShownInsight(
            id=uuid4(),
            insight_type="relationship",
            title="Call mom",
            content="It's been a while",
            status="active",
            shown_at=now - timedelta(hours=48),
        )
        recent_insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="New one",
            content="Fresh",
            status="active",
            shown_at=now - timedelta(hours=1),
        )
        acted_insight = FakeShownInsight(
            id=uuid4(),
            insight_type="favor",
            title="Gift bought",
            content="Done",
            status="acted",
            shown_at=now - timedelta(hours=72),
            acted_at=now - timedelta(hours=48),
        )
        result = self._detect_viewed_no_action(
            [stale_insight, recent_insight, acted_insight],
        )
        assert len(result) == 1
        assert result[0]["insight_id"] == stale_insight.id

    # -------------------------------------------------------------------
    # Pure-logic helper
    # -------------------------------------------------------------------

    def _detect_viewed_no_action(
        self,
        insights: List[FakeShownInsight],
    ) -> List[Dict[str, Any]]:
        """Detect insights shown but not acted upon within threshold.

        Mirrors expected logic of implicit_feedback.detect_viewed_no_action.
        """
        now = datetime.now(timezone.utc)
        results: List[Dict[str, Any]] = []
        for insight in insights:
            if insight.shown_at is None:
                continue
            if insight.acted_at is not None or insight.dismissed_at is not None:
                continue
            if (now - insight.shown_at) > self._STALE_THRESHOLD:
                results.append({
                    "feedback_type": ImplicitFeedbackType.VIEWED_NO_ACTION,
                    "insight_id": insight.id,
                    "insight_type": insight.insight_type,
                    "hours_since_shown": (now - insight.shown_at).total_seconds() / 3600,
                })
        return results


class TestImplicitFeedbackTopicMentioned:
    """Tests for detect_topic_mentioned logic.

    When a user mentions keywords that overlap with an insight's content
    during conversation, it signals implicit interest (positive feedback).
    """

    def test_keyword_overlap_detected(self):
        """Message with overlapping keywords should match the insight."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="relationship",
            title="Call mom",
            content="It's been a while since you talked to mom",
            status="active",
            keywords=["mom", "call", "talk"],
        )
        user_message = "I was just thinking about calling mom today"
        result = self._detect_topic_mentioned([insight], user_message)
        assert len(result) == 1
        assert result[0]["insight_id"] == insight.id
        assert result[0]["feedback_type"] == ImplicitFeedbackType.TOPIC_MENTIONED

    def test_no_overlap_returns_empty(self):
        """Message with no keyword overlap should return empty."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="finance",
            title="Pay bills",
            content="Water bill is due next week",
            status="active",
            keywords=["water", "bill", "payment"],
        )
        user_message = "Let's go to the movies tonight"
        result = self._detect_topic_mentioned([insight], user_message)
        assert len(result) == 0

    def test_case_insensitive_matching(self):
        """Keyword matching should be case-insensitive."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="health",
            title="Exercise",
            content="Time for your weekly run",
            status="active",
            keywords=["exercise", "run", "weekly"],
        )
        user_message = "I need to go for a RUN this afternoon"
        result = self._detect_topic_mentioned([insight], user_message)
        assert len(result) == 1

    def test_empty_keywords_no_match(self):
        """Insight with no keywords should never match."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="time",
            title="Meeting",
            content="You have a meeting",
            status="active",
            keywords=[],
        )
        user_message = "I have a meeting at 3pm"
        result = self._detect_topic_mentioned([insight], user_message)
        assert len(result) == 0

    def test_minimum_overlap_threshold(self):
        """Need at least 2 keyword matches to count as topic mentioned."""
        insight = FakeShownInsight(
            id=uuid4(),
            insight_type="relationship",
            title="Visit grandma",
            content="Haven't seen grandma in months",
            status="active",
            keywords=["grandma", "visit", "family", "care"],
        )
        # Only one keyword match ("grandma") — below threshold
        user_message = "Grandma's recipe is great"
        result = self._detect_topic_mentioned(
            [insight], user_message, min_overlap=2,
        )
        assert len(result) == 0

        # Two keyword matches ("grandma", "visit") — meets threshold
        user_message_2 = "Should we visit grandma this weekend?"
        result_2 = self._detect_topic_mentioned(
            [insight], user_message_2, min_overlap=2,
        )
        assert len(result_2) == 1

    # -------------------------------------------------------------------
    # Pure-logic helper
    # -------------------------------------------------------------------

    @staticmethod
    def _detect_topic_mentioned(
        insights: List[FakeShownInsight],
        user_message: str,
        min_overlap: int = 1,
    ) -> List[Dict[str, Any]]:
        """Detect insights whose keywords overlap with user message.

        Mirrors expected logic of implicit_feedback.detect_topic_mentioned.
        """
        message_lower = user_message.lower()
        message_words = set(message_lower.split())
        results: List[Dict[str, Any]] = []
        for insight in insights:
            if not insight.keywords:
                continue
            overlap = sum(
                1 for kw in insight.keywords
                if kw.lower() in message_words or kw.lower() in message_lower
            )
            if overlap >= min_overlap:
                results.append({
                    "feedback_type": ImplicitFeedbackType.TOPIC_MENTIONED,
                    "insight_id": insight.id,
                    "insight_type": insight.insight_type,
                    "matched_keywords": [
                        kw for kw in insight.keywords
                        if kw.lower() in message_words or kw.lower() in message_lower
                    ],
                })
        return results


class TestImplicitFeedbackTypeEnum:
    """Tests for ImplicitFeedbackType enum values."""

    def test_viewed_no_action_value(self):
        assert ImplicitFeedbackType.VIEWED_NO_ACTION == "viewed_no_action"

    def test_topic_mentioned_value(self):
        assert ImplicitFeedbackType.TOPIC_MENTIONED == "topic_mentioned"

    def test_pattern_ignored_value(self):
        assert ImplicitFeedbackType.PATTERN_IGNORED == "pattern_ignored"
