"""Tests for modules/briefing/services/recommendation_engine.py."""

import dataclasses
from datetime import date, datetime, timedelta, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.modules.briefing.services.recommendation_engine import (
    InsightOrchestratorAdapter,
    Recommendation,
    RecommendationContext,
    RecommendationEngine,
    SmartSuggestionAdapter,
    _DEDUP_SIMILARITY_THRESHOLD,
    _SHOWN_UNACTED_SUPPRESS_COUNT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def family_id():
    return uuid4()


def _make_rec(
    title: str = "Test",
    content: str = "Content",
    rec_type: str = "time",
    priority: float = 0.5,
    source: str = "test",
    shown_count: int = 0,
    last_shown_at=None,
    **meta,
) -> Recommendation:
    return Recommendation(
        id=uuid4(),
        title=title,
        content=content,
        recommendation_type=rec_type,
        priority=priority,
        source_strategy=source,
        metadata=meta,
        shown_count=shown_count,
        last_shown_at=last_shown_at,
    )


def _make_context(
    target_date=None,
    period=None,
    emotional_trend="neutral",
    suppressed_types=None,
    type_weights=None,
) -> RecommendationContext:
    return RecommendationContext(
        target_date=target_date or date(2026, 2, 22),
        period=period,
        emotional_trend=emotional_trend,
        suppressed_types=suppressed_types or [],
        type_weights=type_weights or {},
    )


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


class TestRecommendation:
    def test_frozen(self):
        rec = _make_rec()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.title = "changed"  # type: ignore[misc]

    def test_default_fields(self):
        rec = _make_rec()
        assert rec.shown_count == 0
        assert rec.last_shown_at is None
        assert rec.metadata == {}

    def test_custom_metadata(self):
        rec = _make_rec(urgency="high", icon="star")
        assert rec.metadata["urgency"] == "high"
        assert rec.metadata["icon"] == "star"


# ---------------------------------------------------------------------------
# RecommendationContext dataclass
# ---------------------------------------------------------------------------


class TestRecommendationContext:
    def test_frozen(self):
        ctx = _make_context()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.period = "morning"  # type: ignore[misc]

    def test_defaults(self):
        ctx = _make_context()
        assert ctx.emotional_trend == "neutral"
        assert ctx.density_level == "normal"
        assert ctx.suppressed_types == []
        assert ctx.type_weights == {}


# ---------------------------------------------------------------------------
# Feedback weights (Step 4)
# ---------------------------------------------------------------------------


class TestApplyFeedbackWeights:
    def test_no_weights_unchanged(self):
        recs = [_make_rec(priority=0.5, rec_type="time")]
        ctx = _make_context()
        result = RecommendationEngine._apply_feedback_weights(recs, ctx)
        assert result[0].priority == pytest.approx(0.5)

    def test_weight_boosts_priority(self):
        recs = [_make_rec(priority=0.5, rec_type="time")]
        ctx = _make_context(type_weights={"time": 1.5})
        result = RecommendationEngine._apply_feedback_weights(recs, ctx)
        assert result[0].priority == pytest.approx(0.75)

    def test_weight_reduces_priority(self):
        recs = [_make_rec(priority=0.8, rec_type="gift_reminder")]
        ctx = _make_context(type_weights={"gift_reminder": 0.5})
        result = RecommendationEngine._apply_feedback_weights(recs, ctx)
        assert result[0].priority == pytest.approx(0.4)

    def test_priority_capped_at_1(self):
        recs = [_make_rec(priority=0.9, rec_type="time")]
        ctx = _make_context(type_weights={"time": 2.0})
        result = RecommendationEngine._apply_feedback_weights(recs, ctx)
        assert result[0].priority == pytest.approx(1.0)

    def test_unmatched_type_uses_default_weight(self):
        recs = [_make_rec(priority=0.5, rec_type="unknown_type")]
        ctx = _make_context(type_weights={"time": 1.5})
        result = RecommendationEngine._apply_feedback_weights(recs, ctx)
        assert result[0].priority == pytest.approx(0.5)

    def test_immutability(self):
        original = _make_rec(priority=0.5, rec_type="time")
        ctx = _make_context(type_weights={"time": 1.5})
        result = RecommendationEngine._apply_feedback_weights([original], ctx)
        assert original.priority == 0.5
        assert result[0].priority == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Suppression (Step 6)
# ---------------------------------------------------------------------------


class TestApplySuppression:
    def test_suppressed_type_removed(self):
        recs = [
            _make_rec(rec_type="time"),
            _make_rec(rec_type="favor"),
        ]
        ctx = _make_context(suppressed_types=["favor"])
        result = RecommendationEngine._apply_suppression(recs, ctx)
        assert len(result) == 1
        assert result[0].recommendation_type == "time"

    def test_shown_count_suppression(self):
        now = datetime.now(timezone.utc)
        rec = _make_rec(
            shown_count=_SHOWN_UNACTED_SUPPRESS_COUNT,
            last_shown_at=now - timedelta(days=1),
        )
        ctx = _make_context()
        result = RecommendationEngine._apply_suppression([rec], ctx)
        assert len(result) == 0

    def test_shown_count_suppression_expired(self):
        now = datetime.now(timezone.utc)
        rec = _make_rec(
            shown_count=_SHOWN_UNACTED_SUPPRESS_COUNT,
            last_shown_at=now - timedelta(days=31),
        )
        ctx = _make_context()
        result = RecommendationEngine._apply_suppression([rec], ctx)
        assert len(result) == 1

    def test_negative_emotion_filters_low_priority(self):
        recs = [
            _make_rec(priority=0.2, urgency="low"),
            _make_rec(priority=0.8, urgency="high"),
        ]
        ctx = _make_context(emotional_trend="negative")
        result = RecommendationEngine._apply_suppression(recs, ctx)
        assert len(result) == 1
        assert result[0].priority == 0.8

    def test_neutral_emotion_keeps_all(self):
        recs = [
            _make_rec(priority=0.2, urgency="low"),
            _make_rec(priority=0.8, urgency="high"),
        ]
        ctx = _make_context(emotional_trend="neutral")
        result = RecommendationEngine._apply_suppression(recs, ctx)
        assert len(result) == 2

    def test_empty_input(self):
        ctx = _make_context()
        result = RecommendationEngine._apply_suppression([], ctx)
        assert result == []


# ---------------------------------------------------------------------------
# Title dedup (fallback)
# ---------------------------------------------------------------------------


class TestTitleDedup:
    def test_removes_duplicate_titles(self):
        recs = [
            _make_rec(title="Same Title", priority=0.8),
            _make_rec(title="same title", priority=0.5),
            _make_rec(title="Different"),
        ]
        result = RecommendationEngine._title_dedup(recs)
        assert len(result) == 2
        titles = {r.title for r in result}
        assert "Different" in titles

    def test_empty_list(self):
        assert RecommendationEngine._title_dedup([]) == []

    def test_no_duplicates(self):
        recs = [_make_rec(title="A"), _make_rec(title="B")]
        result = RecommendationEngine._title_dedup(recs)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# InsightOrchestratorAdapter conversion
# ---------------------------------------------------------------------------


class TestInsightOrchestratorAdapter:
    def test_convert_basic(self):
        mock_insight = MagicMock()
        mock_insight.id = uuid4()
        mock_insight.title = "Test Insight"
        mock_insight.content = "Content"
        mock_insight.insight_type = "time"
        mock_insight.importance = 80
        mock_insight.urgency = 60
        mock_insight.importance_score = 80
        mock_insight.urgency_score = 60
        mock_insight.extra_data = {"source": "memory"}
        mock_insight.suggested_action = "set_reminder"
        mock_insight.related_event_id = None
        mock_insight.related_important_date_id = None
        mock_insight.related_person_id = None

        rec = InsightOrchestratorAdapter._convert(mock_insight)

        assert rec.title == "Test Insight"
        assert rec.recommendation_type == "time"
        assert rec.source_strategy == "insight_memory"
        expected_priority = min(1.0, (80 * 0.6 + 60 * 0.4) / 100.0)
        assert rec.priority == pytest.approx(expected_priority)

    def test_convert_missing_extra_data(self):
        mock_insight = MagicMock()
        mock_insight.id = uuid4()
        mock_insight.title = "T"
        mock_insight.content = "C"
        mock_insight.insight_type = "relationship"
        mock_insight.importance = 50
        mock_insight.urgency = 50
        mock_insight.importance_score = 50
        mock_insight.urgency_score = 50
        mock_insight.extra_data = None
        mock_insight.source_context = None
        mock_insight.suggested_action = None
        mock_insight.related_event_id = None
        mock_insight.related_important_date_id = None
        mock_insight.related_person_id = None

        rec = InsightOrchestratorAdapter._convert(mock_insight)
        assert rec.source_strategy == "insight_insight"

    def test_strategy_name(self):
        adapter = InsightOrchestratorAdapter(MagicMock())
        assert adapter.strategy_name == "insight_orchestrator"

    @pytest.mark.asyncio
    async def test_generate_rolls_back_on_failure(self, user_id, family_id):
        mock_db = AsyncMock()
        adapter = InsightOrchestratorAdapter(mock_db)

        with patch(
            "src.modules.briefing.services.insight_orchestrator.InsightOrchestrator"
        ) as mock_orch_cls:
            mock_orch = mock_orch_cls.return_value
            mock_orch.generate_all = AsyncMock(side_effect=RuntimeError("boom"))

            recs = await adapter.generate(user_id, family_id, _make_context())

        assert recs == []
        mock_db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# SmartSuggestionAdapter conversion
# ---------------------------------------------------------------------------


class TestSmartSuggestionAdapter:
    def test_convert_basic(self):
        mock_suggestion = MagicMock()
        mock_suggestion.id = str(uuid4())
        mock_suggestion.title = "Buy Gift"
        mock_suggestion.content = "Consider a gift"
        mock_suggestion.type = MagicMock(value="gift_reminder")
        mock_suggestion.priority = 75
        mock_suggestion.icon = "card_giftcard"
        mock_suggestion.action_options = ["prepare_gift", "ignore"]
        mock_suggestion.action_data = {"budget": 200}
        mock_suggestion.urgency = "normal"
        mock_suggestion.related_event_ids = []
        mock_suggestion.related_member_ids = []

        rec = SmartSuggestionAdapter._convert(mock_suggestion)

        assert rec.title == "Buy Gift"
        assert rec.recommendation_type == "gift_reminder"
        assert rec.priority == pytest.approx(0.75)
        assert rec.source_strategy == "smart_suggestion"
        assert rec.metadata["icon"] == "card_giftcard"

    def test_convert_string_type(self):
        mock_suggestion = MagicMock()
        mock_suggestion.id = str(uuid4())
        mock_suggestion.title = "T"
        mock_suggestion.content = "C"
        mock_suggestion.type = "curation"
        mock_suggestion.priority = 50
        mock_suggestion.icon = "info"
        mock_suggestion.action_options = []
        mock_suggestion.action_data = {}
        mock_suggestion.urgency = "low"
        mock_suggestion.related_event_ids = []
        mock_suggestion.related_member_ids = []

        rec = SmartSuggestionAdapter._convert(mock_suggestion)
        assert rec.recommendation_type == "curation"

    def test_strategy_name(self):
        adapter = SmartSuggestionAdapter(MagicMock())
        assert adapter.strategy_name == "smart_suggestion"


# ---------------------------------------------------------------------------
# Full pipeline (async)
# ---------------------------------------------------------------------------


class TestRecommendationEnginePipeline:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_generate_empty_strategies(self, mock_db, user_id, family_id):
        engine = RecommendationEngine(mock_db)
        engine._strategies = []
        result = await engine.generate(user_id, family_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_with_mock_strategy(self, mock_db, user_id, family_id):
        engine = RecommendationEngine(mock_db)

        mock_strategy = MagicMock()
        mock_strategy.strategy_name = "test"
        mock_strategy.generate = AsyncMock(return_value=[
            _make_rec(title="Rec1", priority=0.8),
            _make_rec(title="Rec2", priority=0.3),
        ])

        engine._strategies = [mock_strategy]

        # Patch _build_context to avoid DB calls
        engine._build_context = AsyncMock(return_value=_make_context())
        # Patch semantic dedup to use title dedup
        engine._semantic_dedup = AsyncMock(
            side_effect=lambda recs: RecommendationEngine._title_dedup(recs)
        )

        result = await engine.generate(user_id, family_id)

        assert len(result) == 2
        assert result[0].priority >= result[1].priority

    @pytest.mark.asyncio
    async def test_generate_respects_limit(self, mock_db, user_id, family_id):
        engine = RecommendationEngine(mock_db)

        recs = [_make_rec(title=f"R{i}", priority=0.5) for i in range(20)]
        mock_strategy = MagicMock()
        mock_strategy.strategy_name = "test"
        mock_strategy.generate = AsyncMock(return_value=recs)

        engine._strategies = [mock_strategy]
        engine._build_context = AsyncMock(return_value=_make_context())
        engine._semantic_dedup = AsyncMock(
            side_effect=lambda r: RecommendationEngine._title_dedup(r)
        )

        result = await engine.generate(user_id, family_id, limit=5)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_generate_strategy_failure_graceful(self, mock_db, user_id, family_id):
        engine = RecommendationEngine(mock_db)

        failing = MagicMock()
        failing.strategy_name = "failing"
        failing.generate = AsyncMock(side_effect=RuntimeError("boom"))

        working = MagicMock()
        working.strategy_name = "working"
        working.generate = AsyncMock(return_value=[_make_rec(title="OK")])

        engine._strategies = [failing, working]
        engine._build_context = AsyncMock(return_value=_make_context())
        engine._semantic_dedup = AsyncMock(
            side_effect=lambda r: RecommendationEngine._title_dedup(r)
        )

        result = await engine.generate(user_id, family_id)
        assert len(result) == 1
        assert result[0].title == "OK"

    @pytest.mark.asyncio
    async def test_generate_applies_suppression(self, mock_db, user_id, family_id):
        engine = RecommendationEngine(mock_db)

        recs = [
            _make_rec(title="Good", rec_type="time", priority=0.8),
            _make_rec(title="Suppressed", rec_type="favor", priority=0.9),
        ]
        mock_strategy = MagicMock()
        mock_strategy.strategy_name = "test"
        mock_strategy.generate = AsyncMock(return_value=recs)

        engine._strategies = [mock_strategy]
        engine._build_context = AsyncMock(
            return_value=_make_context(suppressed_types=["favor"])
        )
        engine._semantic_dedup = AsyncMock(
            side_effect=lambda r: RecommendationEngine._title_dedup(r)
        )

        result = await engine.generate(user_id, family_id)
        assert len(result) == 1
        assert result[0].title == "Good"

    @pytest.mark.asyncio
    async def test_generate_applies_type_weights(self, mock_db, user_id, family_id):
        engine = RecommendationEngine(mock_db)

        recs = [
            _make_rec(title="Boosted", rec_type="time", priority=0.5),
            _make_rec(title="Normal", rec_type="memory", priority=0.5),
        ]
        mock_strategy = MagicMock()
        mock_strategy.strategy_name = "test"
        mock_strategy.generate = AsyncMock(return_value=recs)

        engine._strategies = [mock_strategy]
        engine._build_context = AsyncMock(
            return_value=_make_context(type_weights={"time": 1.8})
        )
        engine._semantic_dedup = AsyncMock(
            side_effect=lambda r: RecommendationEngine._title_dedup(r)
        )

        result = await engine.generate(user_id, family_id)
        assert len(result) == 2
        # "Boosted" should be first (0.5 * 1.8 = 0.9 > 0.5)
        assert result[0].title == "Boosted"
        assert result[0].priority == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Semantic dedup (_semantic_dedup / _semantic_dedup_with_embeddings)
# ---------------------------------------------------------------------------


class TestSemanticDedup:

    @pytest.mark.asyncio
    async def test_similar_recommendations_merged(self):
        engine = RecommendationEngine(AsyncMock())
        rec1 = _make_rec(title="Buy flowers", content="Get flowers for mom", priority=0.8)
        rec2 = _make_rec(title="Get bouquet", content="Pick up a bouquet for mother", priority=0.5)

        mock_service = MagicMock()
        mock_service.get_embeddings_batch = AsyncMock(
            return_value=[[1.0, 0.0], [0.98, 0.2]],
        )
        mock_service.compute_similarity = MagicMock(return_value=0.9)

        with patch(
            "src.modules.memory.embedding_service.EmbeddingService",
            return_value=mock_service,
        ):
            result = await engine._semantic_dedup([rec1, rec2])

        assert len(result) == 1
        # Higher priority (0.8) should survive
        assert result[0].priority == 0.8

    @pytest.mark.asyncio
    async def test_dissimilar_recommendations_kept(self):
        engine = RecommendationEngine(AsyncMock())
        rec1 = _make_rec(title="Buy flowers", content="Get flowers for mom", priority=0.8)
        rec2 = _make_rec(title="Book flight", content="Reserve ticket to Beijing", priority=0.6)

        mock_service = MagicMock()
        mock_service.get_embeddings_batch = AsyncMock(
            return_value=[[1.0, 0.0], [0.0, 1.0]],
        )
        mock_service.compute_similarity = MagicMock(return_value=0.3)

        with patch(
            "src.modules.memory.embedding_service.EmbeddingService",
            return_value=mock_service,
        ):
            result = await engine._semantic_dedup([rec1, rec2])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_embedding_failure_falls_back_to_title(self):
        engine = RecommendationEngine(AsyncMock())
        rec1 = _make_rec(title="Same Title", content="Content A", priority=0.8)
        rec2 = _make_rec(title="same title", content="Content B", priority=0.5)
        rec3 = _make_rec(title="Different", content="Content C", priority=0.6)

        with patch(
            "src.modules.memory.embedding_service.EmbeddingService",
            side_effect=RuntimeError("Embedding service down"),
        ):
            result = await engine._semantic_dedup([rec1, rec2, rec3])

        # Falls back to title dedup: "Same Title" and "same title" merge
        assert len(result) == 2
        titles = {r.title for r in result}
        assert "Different" in titles

    @pytest.mark.asyncio
    async def test_higher_priority_wins_merge(self):
        engine = RecommendationEngine(AsyncMock())
        rec_low = _make_rec(title="Reminder A", content="Low priority item", priority=0.3)
        rec_high = _make_rec(title="Reminder B", content="High priority item", priority=0.9)

        mock_service = MagicMock()
        mock_service.get_embeddings_batch = AsyncMock(
            return_value=[[1.0, 0.0], [0.99, 0.1]],
        )
        mock_service.compute_similarity = MagicMock(return_value=0.9)

        with patch(
            "src.modules.memory.embedding_service.EmbeddingService",
            return_value=mock_service,
        ):
            result = await engine._semantic_dedup([rec_low, rec_high])

        assert len(result) == 1
        assert result[0].priority == 0.9
        assert result[0].title == "Reminder B"
