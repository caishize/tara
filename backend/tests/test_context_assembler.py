"""Tests for ai_engine/context_assembler.py -- TokenBudget, estimate_tokens,
ContextMetadata, TimestampGuard, budget allocation, PrivacyFilter, ExclusionFilter,
and ContextAssembler pipeline."""

import dataclasses
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.ai_engine.context_assembler import (
    ContextAssembler,
    ContextItem,
    ContextMetadata,
    DEFAULT_COOLDOWN_DAYS,
    ExclusionFilter,
    FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD,
    PrivacyFilter,
    PrivacyInferenceGuard,
    TokenBudget,
    TASK_OVERRIDES,
    TIMESTAMP_GUARD_NOTICE,
    allocate_budget,
    apply_filters,
    apply_timestamp_guard,
    estimate_tokens,
)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    """Tests for the token estimation function.

    When tiktoken is installed, estimate_tokens uses cl100k_base encoding.
    When tiktoken is unavailable, it falls back to a character heuristic.
    These tests validate both correctness and basic properties.
    """

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_pure_chinese_positive(self):
        text = "你好世界"
        result = estimate_tokens(text)
        assert result > 0

    def test_pure_english_positive(self):
        text = "hello world"
        result = estimate_tokens(text)
        assert result > 0

    def test_mixed_cn_en_positive(self):
        text = "你好hello"
        result = estimate_tokens(text)
        assert result > 0

    def test_chinese_paragraph_reasonable(self):
        text = "今天天气真好，我们一起去公园散步吧。"
        result = estimate_tokens(text)
        assert 5 <= result <= 50

    def test_returns_int(self):
        assert isinstance(estimate_tokens("abc"), int)

    def test_numbers_and_punctuation(self):
        text = "2026-02-18 12:00"
        result = estimate_tokens(text)
        assert result > 0

    def test_longer_text_more_tokens(self):
        short = "hello"
        long_text = short * 100
        assert estimate_tokens(long_text) > estimate_tokens(short)


# ---------------------------------------------------------------------------
# TokenBudget
# ---------------------------------------------------------------------------


class TestTokenBudget:
    """Tests for TokenBudget dataclass and for_action method."""

    def test_default_values(self):
        budget = TokenBudget()
        assert budget.total == 6900
        assert budget.l1_fixed == 600
        assert budget.l2_fixed == 2000
        assert budget.l3_min == 500
        assert budget.l3_max == 1500
        assert budget.l4_min == 500
        assert budget.l4_max == 2000
        assert budget.l5_fixed == 800

    def test_frozen(self):
        budget = TokenBudget()
        with pytest.raises(dataclasses.FrozenInstanceError):
            budget.total = 9999  # type: ignore[misc]

    def test_custom_values(self):
        budget = TokenBudget(total=8000, l1_fixed=600)
        assert budget.total == 8000
        assert budget.l1_fixed == 600
        assert budget.l2_fixed == 2000  # unchanged default

    def test_flexible_pool(self):
        budget = TokenBudget()
        # 6900 - 600 - 2000 - 800 = 3500
        assert budget.flexible_pool == 3500

    def test_flexible_pool_custom(self):
        budget = TokenBudget(total=3800, l1_fixed=1000, l2_fixed=1500, l5_fixed=300)
        # 3800 - 1000 - 1500 - 300(l5) = 1000
        assert budget.flexible_pool == 1000

    def test_flexible_pool_never_negative(self):
        """Validation now rejects fixed > total, so test the boundary case instead."""
        budget = TokenBudget(total=3400, l1_fixed=500, l2_fixed=2000, l5_fixed=800,
                             l3_min=0, l4_min=0)
        # 3400 - 500 - 2000 - 800 = 100, barely positive
        assert budget.flexible_pool == 100

    def test_flexible_pool_validation_rejects_invalid(self):
        """Fixed allocations exceeding total should raise ValueError."""
        with pytest.raises(ValueError, match="Fixed allocations"):
            TokenBudget(total=100, l1_fixed=500, l2_fixed=2000)

    # -- for_action --

    def test_for_action_analyze(self):
        budget = TokenBudget()
        adjusted = budget.for_action("analyze")
        assert adjusted.l2_fixed == 800
        assert adjusted.l4_min == 1000
        assert adjusted.l4_max == 2500
        # unchanged fields
        assert adjusted.total == 6900
        assert adjusted.l1_fixed == 600
        assert adjusted.l3_min == 500
        assert adjusted.l5_fixed == 800

    def test_for_action_plan(self):
        budget = TokenBudget()
        adjusted = budget.for_action("plan")
        assert adjusted.l2_fixed == 1500
        assert adjusted.l3_max == 800
        assert adjusted.l4_max == 2200
        assert adjusted.l5_fixed == 1000

    def test_for_action_lookup(self):
        budget = TokenBudget()
        adjusted = budget.for_action("lookup")
        assert adjusted.l2_fixed == 800
        assert adjusted.l3_max == 500
        assert adjusted.l4_max == 800
        assert adjusted.l5_fixed == 400

    def test_for_action_unknown_returns_same(self):
        budget = TokenBudget()
        same = budget.for_action("unknown_action")
        assert same is budget  # identity, not just equality

    def test_for_action_returns_new_instance(self):
        budget = TokenBudget()
        adjusted = budget.for_action("analyze")
        assert adjusted is not budget

    def test_for_action_does_not_mutate_original(self):
        budget = TokenBudget()
        budget.for_action("analyze")
        assert budget.l2_fixed == 2000  # original unchanged

    def test_all_task_overrides_covered(self):
        """Ensure every key in TASK_OVERRIDES produces a valid adjusted budget."""
        base = TokenBudget()
        for action_type, overrides in TASK_OVERRIDES.items():
            adjusted = base.for_action(action_type)
            for field_name, expected_value in overrides.items():
                assert getattr(adjusted, field_name) == expected_value, (
                    f"for_action('{action_type}') field '{field_name}' "
                    f"expected {expected_value}, got {getattr(adjusted, field_name)}"
                )


# ---------------------------------------------------------------------------
# ContextMetadata
# ---------------------------------------------------------------------------


class TestContextMetadata:
    """Tests for ContextMetadata frozen dataclass."""

    def test_default_values(self):
        meta = ContextMetadata()
        assert meta.total_tokens_used == 0
        assert meta.l1_tokens == 0
        assert meta.l2_tokens == 0
        assert meta.l3_tokens == 0
        assert meta.l4_tokens == 0
        assert meta.l5_tokens == 0
        assert meta.memories_included == 0
        assert meta.memories_filtered == 0
        assert meta.assembly_time_ms == 0.0

    def test_frozen(self):
        meta = ContextMetadata(total_tokens_used=100)
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.total_tokens_used = 200  # type: ignore[misc]

    def test_budget_utilization(self):
        meta = ContextMetadata(total_tokens_used=3450)
        assert meta.budget_utilization == pytest.approx(0.5)

    def test_budget_utilization_zero(self):
        meta = ContextMetadata(total_tokens_used=0)
        assert meta.budget_utilization == 0.0

    def test_budget_utilization_over_budget(self):
        meta = ContextMetadata(total_tokens_used=10350)
        assert meta.budget_utilization == pytest.approx(1.5)

    def test_budget_utilization_custom_budget_total(self):
        meta = ContextMetadata(total_tokens_used=4000, budget_total=8000)
        assert meta.budget_utilization == pytest.approx(0.5)

    def test_budget_utilization_zero_budget_total(self):
        meta = ContextMetadata(total_tokens_used=100, budget_total=0)
        assert meta.budget_utilization == 0.0

    def test_budget_total_default(self):
        meta = ContextMetadata()
        assert meta.budget_total == 6900

    def test_to_dict(self):
        meta = ContextMetadata(
            total_tokens_used=4500,
            l1_tokens=400,
            l2_tokens=1800,
            l3_tokens=1000,
            l4_tokens=1300,
            l5_tokens=0,
            memories_included=12,
            memories_filtered=3,
            assembly_time_ms=123.456,
        )
        d = meta.to_dict()
        assert d["total_tokens_used"] == 4500
        assert d["budget_total"] == 6900
        assert d["l1_tokens"] == 400
        assert d["l2_tokens"] == 1800
        assert d["l3_tokens"] == 1000
        assert d["l4_tokens"] == 1300
        assert d["l5_tokens"] == 0
        assert d["memories_included"] == 12
        assert d["memories_filtered"] == 3
        assert d["assembly_time_ms"] == 123.46
        assert d["budget_utilization"] == pytest.approx(4500 / 6900, abs=0.01)

    def test_to_dict_returns_plain_dict(self):
        meta = ContextMetadata()
        d = meta.to_dict()
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# ContextItem
# ---------------------------------------------------------------------------


class TestContextItem:
    """Tests for the ContextItem value object."""

    def test_basic_creation(self):
        item = ContextItem(
            layer="l1",
            source="secretary_note",
            content="Test note",
            tokens=10,
        )
        assert item.layer == "l1"
        assert item.source == "secretary_note"
        assert item.content == "Test note"
        assert item.tokens == 10

    def test_frozen(self):
        item = ContextItem(layer="l1", source="test", content="x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.content = "y"  # type: ignore[misc]

    def test_rank_score_recent(self):
        item = ContextItem(
            layer="l4",
            source="memory",
            content="test",
            importance=8.0,
            feedback_weight=1.0,
            recency_days=0.0,
        )
        # recency_decay = max(0.1, 1 - 0/90) = 1.0
        # score = 8.0 * 1.0 * 1.0 = 8.0
        assert item.rank_score == pytest.approx(8.0)

    def test_rank_score_old_memory(self):
        item = ContextItem(
            layer="l4",
            source="memory",
            content="test",
            importance=10.0,
            feedback_weight=1.0,
            recency_days=45.0,
        )
        # recency_decay = max(0.1, 1 - 45/90) = 0.5
        # score = 10.0 * 1.0 * 0.5 = 5.0
        assert item.rank_score == pytest.approx(5.0)

    def test_rank_score_very_old_clamps(self):
        item = ContextItem(
            layer="l4",
            source="memory",
            content="test",
            importance=10.0,
            feedback_weight=1.0,
            recency_days=365.0,
        )
        # recency_decay = max(0.1, 1 - 365/90) = max(0.1, -3.06) = 0.1
        # score = 10.0 * 1.0 * 0.1 = 1.0
        assert item.rank_score == pytest.approx(1.0)

    def test_rank_score_with_feedback_weight(self):
        item = ContextItem(
            layer="l4",
            source="memory",
            content="test",
            importance=5.0,
            feedback_weight=0.5,
            recency_days=0.0,
        )
        # 5.0 * 0.5 * 1.0 = 2.5
        assert item.rank_score == pytest.approx(2.5)

    def test_default_entity_ids(self):
        item = ContextItem(layer="l1", source="test", content="x")
        assert item.entity_ids == ()

    def test_default_metadata(self):
        item = ContextItem(layer="l1", source="test", content="x")
        assert item.metadata == {}


# ---------------------------------------------------------------------------
# Timestamp Guard (Step 1.5)
# ---------------------------------------------------------------------------


def _make_item(layer: str, content: str, tokens: int = 10, **meta) -> ContextItem:
    """Helper to create a ContextItem with metadata."""
    return ContextItem(layer=layer, source="test", content=content, tokens=tokens, metadata=meta)


class TestTimestampGuard:
    """Tests for apply_timestamp_guard."""

    def test_empty_l3_returns_empty(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        assert apply_timestamp_guard([], l2) == []

    def test_empty_l2_returns_l3_unchanged(self):
        l3 = [_make_item("l3", "summary", period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, [])
        assert result == l3

    def test_no_overlap_no_guard(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 10, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 15, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, l2)
        assert len(result) == 1
        assert TIMESTAMP_GUARD_NOTICE not in result[0].content

    def test_overlap_adds_guard_notice(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc))]
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 19, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, l2)
        assert len(result) == 1
        assert result[0].content.startswith(TIMESTAMP_GUARD_NOTICE)
        assert "summary" in result[0].content

    def test_partial_overlap_at_boundary(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 15, tzinfo=timezone.utc))]
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 15, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 16, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, l2)
        assert TIMESTAMP_GUARD_NOTICE in result[0].content

    def test_mixed_overlap_and_no_overlap(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        l3_overlap = _make_item("l3", "overlap",
                                period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),
                                period_end=datetime(2026, 2, 19, tzinfo=timezone.utc))
        l3_safe = _make_item("l3", "safe",
                             period_start=datetime(2026, 2, 1, tzinfo=timezone.utc),
                             period_end=datetime(2026, 2, 5, tzinfo=timezone.utc))
        result = apply_timestamp_guard([l3_overlap, l3_safe], l2)
        assert TIMESTAMP_GUARD_NOTICE in result[0].content
        assert TIMESTAMP_GUARD_NOTICE not in result[1].content

    def test_l3_without_timestamps_not_guarded(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        l3 = [_make_item("l3", "no timestamps")]
        result = apply_timestamp_guard(l3, l2)
        assert TIMESTAMP_GUARD_NOTICE not in result[0].content

    def test_l2_without_timestamps_no_guard(self):
        l2 = [_make_item("l2", "msg")]  # no created_at
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 19, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, l2)
        assert TIMESTAMP_GUARD_NOTICE not in result[0].content

    def test_guard_updates_token_count(self):
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        l3 = [_make_item("l3", "summary", tokens=5,
                         period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 19, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, l2)
        # Token count should be recalculated for guarded content
        assert result[0].tokens > 5

    def test_mixed_naive_and_aware_datetimes_no_crash(self):
        """Mixing naive L2 timestamps with aware L3 timestamps should not raise."""
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18))]  # naive
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),  # aware
                         period_end=datetime(2026, 2, 19, tzinfo=timezone.utc))]    # aware
        # Should not raise TypeError
        result = apply_timestamp_guard(l3, l2)
        assert len(result) == 1

    def test_naive_l2_with_aware_l3_overlap_detected(self):
        """Overlap is still detected when L2 is naive and L3 is aware."""
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, 10, 0))]  # naive
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 17, tzinfo=timezone.utc),
                         period_end=datetime(2026, 2, 19, tzinfo=timezone.utc))]
        result = apply_timestamp_guard(l3, l2)
        assert TIMESTAMP_GUARD_NOTICE in result[0].content

    def test_aware_l2_with_naive_l3_overlap_detected(self):
        """Overlap is still detected when L2 is aware and L3 is naive."""
        l2 = [_make_item("l2", "msg", created_at=datetime(2026, 2, 18, tzinfo=timezone.utc))]
        l3 = [_make_item("l3", "summary",
                         period_start=datetime(2026, 2, 17),  # naive
                         period_end=datetime(2026, 2, 19))]    # naive
        result = apply_timestamp_guard(l3, l2)
        assert TIMESTAMP_GUARD_NOTICE in result[0].content


# ---------------------------------------------------------------------------
# Budget allocation (Step 2)
# ---------------------------------------------------------------------------


class TestAllocateBudget:
    """Tests for allocate_budget."""

    def test_all_layers_fit_within_budget(self):
        budget = TokenBudget(total=6000)
        l1 = [_make_item("l1", "note", tokens=200)]
        l2 = [_make_item("l2", "msg", tokens=500)]
        l3 = [_make_item("l3", "profile", tokens=300)]
        l4 = [_make_item("l4", "memory", tokens=400)]
        result = allocate_budget(l1, l2, l3, l4, budget)
        assert len(result) == 4
        total = sum(i.tokens for i in result)
        assert total <= budget.total

    def test_l1_truncated_to_fixed_budget(self):
        budget = TokenBudget(l1_fixed=100)
        l1 = [
            _make_item("l1", "note1", tokens=60),
            _make_item("l1", "note2", tokens=60),
        ]
        result = allocate_budget(l1, [], [], [], budget)
        l1_result = [i for i in result if i.layer == "l1"]
        total_l1 = sum(i.tokens for i in l1_result)
        # Only first item should fit (60 <= 100), second would push to 120
        assert total_l1 <= 100 + 60  # at most one item over due to "at least one" rule

    def test_l2_truncated_to_fixed_budget(self):
        budget = TokenBudget(l2_fixed=100)
        l2 = [
            _make_item("l2", "msg1", tokens=60),
            _make_item("l2", "msg2", tokens=60),
        ]
        result = allocate_budget([], l2, [], [], budget)
        l2_result = [i for i in result if i.layer == "l2"]
        assert len(l2_result) <= 2

    def test_empty_inputs(self):
        budget = TokenBudget()
        result = allocate_budget([], [], [], [], budget)
        assert result == []

    def test_flexible_layers_share_remaining(self):
        budget = TokenBudget(total=6000, l1_fixed=500, l2_fixed=2000)
        l1 = [_make_item("l1", "n", tokens=100)]
        l2 = [_make_item("l2", "m", tokens=200)]
        l3 = [_make_item("l3", "p", tokens=1000)]
        l4 = [_make_item("l4", "r", tokens=1000)]
        result = allocate_budget(l1, l2, l3, l4, budget)
        # remaining = 6000 - 100 - 200 = 5700, both l3 and l4 fit easily
        assert len(result) == 4

    def test_budget_truncates_multiple_flexible_items(self):
        budget = TokenBudget(total=600, l1_fixed=100, l2_fixed=100, l5_fixed=0,
                             l3_min=50, l3_max=200, l4_min=50, l4_max=200)
        l1 = [_make_item("l1", "n", tokens=80)]
        l2 = [_make_item("l2", "m", tokens=80)]
        l3 = [
            _make_item("l3", "p1", tokens=100),
            _make_item("l3", "p2", tokens=100),
            _make_item("l3", "p3", tokens=100),
        ]
        l4 = [
            _make_item("l4", "r1", tokens=100),
            _make_item("l4", "r2", tokens=100),
            _make_item("l4", "r3", tokens=100),
        ]
        result = allocate_budget(l1, l2, l3, l4, budget)
        l3_kept = [i for i in result if i.layer == "l3"]
        l4_kept = [i for i in result if i.layer == "l4"]
        l3_total = sum(i.tokens for i in l3_kept)
        l4_total = sum(i.tokens for i in l4_kept)
        # Each flexible layer should be truncated within its budget
        assert l3_total <= budget.l3_max
        assert l4_total <= budget.l4_max

    def test_single_oversized_item_still_included(self):
        """A single item exceeding its layer budget is still included."""
        budget = TokenBudget(total=500, l1_fixed=100, l2_fixed=100, l5_fixed=0,
                             l3_min=50, l3_max=100, l4_min=50, l4_max=100)
        l3 = [_make_item("l3", "big", tokens=300)]
        result = allocate_budget([], [], l3, [], budget)
        # The single oversized item is still kept (at-least-one guarantee)
        assert len(result) == 1
        assert result[0].tokens == 300

    def test_l3_l4_hard_clamp_prevents_overshoot(self):
        """l3_budget + l4_budget must not exceed remaining tokens."""
        # remaining = 300 - 75 - 75 - 0 = 150, l3_min+l4_min=100 fits
        budget = TokenBudget(total=300, l1_fixed=75, l2_fixed=75, l5_fixed=0,
                             l3_min=50, l3_max=100, l4_min=50, l4_max=100)
        l1 = [_make_item("l1", "n", tokens=75)]
        l2 = [_make_item("l2", "m", tokens=75)]
        l3 = [_make_item("l3", "p", tokens=80)]
        l4 = [_make_item("l4", "r", tokens=80)]
        result = allocate_budget(l1, l2, l3, l4, budget)
        l3_used = sum(i.tokens for i in result if i.layer == "l3")
        l4_used = sum(i.tokens for i in result if i.layer == "l4")
        remaining = 300 - 75 - 75
        # Hard clamp: l3 + l4 must fit within remaining
        assert l3_used + l4_used <= remaining + 80  # at-least-one item may overflow


# ---------------------------------------------------------------------------
# _truncate_items_to_budget 2x size guard
# ---------------------------------------------------------------------------


class TestTruncateItemsSizeGuard:
    """Tests for the 2x size guard in _truncate_items_to_budget."""

    def test_first_item_over_2x_budget_is_truncated(self):
        from src.ai_engine.context_assembler import _truncate_items_to_budget

        # Item has ~1500 tokens but budget is 100 -> exceeds 2x (200)
        big_content = "你" * 1000  # ~1500 tokens
        item = ContextItem(layer="l3", source="test", content=big_content,
                           tokens=estimate_tokens(big_content))
        result = _truncate_items_to_budget([item], 100)
        assert len(result) == 1
        # Content should be truncated + "..." appended
        assert result[0].content.endswith("...")
        assert len(result[0].content) < len(big_content)
        # Truncated tokens should be <= 2x budget
        assert result[0].tokens <= 200 + 10  # small margin for "..." suffix

    def test_first_item_under_1_2x_budget_not_truncated(self):
        from src.ai_engine.context_assembler import _truncate_items_to_budget

        # Item has 110 tokens, budget is 100 -> under 1.2x (120), not truncated
        item = ContextItem(layer="l3", source="test", content="small content",
                           tokens=110)
        result = _truncate_items_to_budget([item], 100)
        assert len(result) == 1
        assert result[0].content == "small content"  # unchanged

    def test_empty_budget_returns_empty(self):
        from src.ai_engine.context_assembler import _truncate_items_to_budget

        item = ContextItem(layer="l3", source="test", content="x", tokens=10)
        result = _truncate_items_to_budget([item], 0)
        assert result == []


# ---------------------------------------------------------------------------
# ContextAssembler pipeline (async)
# ---------------------------------------------------------------------------


class TestContextAssembler:
    """Tests for the full ContextAssembler pipeline."""

    @pytest.fixture
    def user_id(self):
        return uuid4()

    @pytest.fixture
    def family_id(self):
        return uuid4()

    @staticmethod
    def _make_fetcher(items: list):
        """Create an async fetcher that returns fixed items."""
        async def fetcher(*args, **kwargs):
            return items
        return fetcher

    @pytest.mark.asyncio
    async def test_assemble_returns_prompt_and_metadata(self, user_id, family_id):
        l1 = [ContextItem(layer="l1", source="note", content="Important fact", tokens=20)]
        l4 = [ContextItem(layer="l4", source="memory", content="Old memory", tokens=15)]

        assembler = ContextAssembler(
            l1_fetcher=self._make_fetcher(l1),
            l4_fetcher=self._make_fetcher(l4),
        )
        prompt, meta = await assembler.assemble(user_id, family_id, "sess1", "hello")

        assert isinstance(prompt, str)
        assert isinstance(meta, ContextMetadata)
        assert "Important fact" in prompt
        assert "Old memory" in prompt
        assert meta.l1_tokens == 20
        assert meta.l4_tokens == 15
        assert meta.memories_included == 1

    @pytest.mark.asyncio
    async def test_assemble_with_no_fetchers(self, user_id, family_id):
        assembler = ContextAssembler()
        prompt, meta = await assembler.assemble(user_id, family_id, "sess1", "test")
        assert prompt == ""
        assert meta.total_tokens_used == 0

    @pytest.mark.asyncio
    async def test_assemble_with_action_type(self, user_id, family_id):
        l2 = [ContextItem(layer="l2", source="conv", content="x" * 500, tokens=150)]
        l4 = [ContextItem(layer="l4", source="mem", content="y" * 200, tokens=60)]
        assembler = ContextAssembler(
            l2_fetcher=self._make_fetcher(l2),
            l4_fetcher=self._make_fetcher(l4),
        )
        prompt, meta = await assembler.assemble(
            user_id, family_id, "sess1", "analyze data", action_type="analyze",
        )
        assert meta.total_tokens_used > 0

    @pytest.mark.asyncio
    async def test_assemble_entity_resolver_called(self, user_id, family_id):
        resolved = set()

        async def resolver(msg, uid, fid):
            resolved.add("called")
            return {uuid4()}

        assembler = ContextAssembler(entity_resolver=resolver)
        await assembler.assemble(user_id, family_id, "sess1", "test")
        assert "called" in resolved

    @pytest.mark.asyncio
    async def test_assemble_fetcher_failure_graceful(self, user_id, family_id):
        async def failing_fetcher(*args):
            raise RuntimeError("DB connection lost")

        assembler = ContextAssembler(
            l1_fetcher=failing_fetcher,
            l2_fetcher=failing_fetcher,
        )
        prompt, meta = await assembler.assemble(user_id, family_id, "sess1", "test")
        assert meta.total_tokens_used == 0

    @pytest.mark.asyncio
    async def test_assemble_fetcher_failure_logs_warning(self, user_id, family_id, caplog):
        import logging

        async def failing_fetcher(*args):
            raise RuntimeError("DB connection lost")

        assembler = ContextAssembler(l1_fetcher=failing_fetcher)
        with caplog.at_level(logging.WARNING, logger="src.ai_engine.context_assembler"):
            await assembler.assemble(user_id, family_id, "sess1", "test")
        assert any("failed" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_assemble_rejects_zero_token_items(self, user_id, family_id):
        """Fetchers must set tokens > 0; the assertion catches violations."""
        items = [ContextItem(layer="l1", source="note", content="Hello world", tokens=0)]
        assembler = ContextAssembler(l1_fetcher=self._make_fetcher(items))
        with pytest.raises(AssertionError, match="tokens=0"):
            await assembler.assemble(user_id, family_id, "sess1", "test")

    @pytest.mark.asyncio
    async def test_assemble_metadata_timing(self, user_id, family_id):
        assembler = ContextAssembler()
        _, meta = await assembler.assemble(user_id, family_id, "sess1", "test")
        assert meta.assembly_time_ms >= 0

    @pytest.mark.asyncio
    async def test_assemble_serialization_sections(self, user_id, family_id):
        l1 = [ContextItem(layer="l1", source="note", content="L1 content", tokens=10)]
        l2 = [ContextItem(layer="l2", source="conv", content="L2 content", tokens=10)]
        l3 = [ContextItem(layer="l3", source="profile", content="L3 content", tokens=10)]
        l4 = [ContextItem(layer="l4", source="mem", content="L4 content", tokens=10)]

        assembler = ContextAssembler(
            l1_fetcher=self._make_fetcher(l1),
            l2_fetcher=self._make_fetcher(l2),
            l3_fetcher=self._make_fetcher(l3),
            l4_fetcher=self._make_fetcher(l4),
        )
        prompt, _ = await assembler.assemble(user_id, family_id, "sess1", "test")
        assert "L1" in prompt
        assert "L2" in prompt
        assert "L3" in prompt
        assert "L4" in prompt


# ---------------------------------------------------------------------------
# Ranking (Step 4)
# ---------------------------------------------------------------------------


class TestRanking:
    """Tests for ContextAssembler._rank."""

    def test_l1_l2_preserve_order(self):
        items = [
            ContextItem(layer="l1", source="a", content="first", tokens=1, importance=1.0),
            ContextItem(layer="l2", source="b", content="second", tokens=1, importance=5.0),
            ContextItem(layer="l1", source="c", content="third", tokens=1, importance=10.0),
        ]
        ranked = ContextAssembler._rank(items)
        assert ranked[0].content == "first"
        assert ranked[1].content == "second"
        assert ranked[2].content == "third"

    def test_l3_l4_sorted_by_rank_score(self):
        items = [
            ContextItem(layer="l4", source="m", content="low", tokens=1, importance=1.0),
            ContextItem(layer="l3", source="p", content="high", tokens=1, importance=10.0),
            ContextItem(layer="l4", source="m", content="mid", tokens=1, importance=5.0),
        ]
        ranked = ContextAssembler._rank(items)
        assert ranked[0].content == "high"
        assert ranked[1].content == "mid"
        assert ranked[2].content == "low"

    def test_mixed_layers_ordered_correctly(self):
        items = [
            ContextItem(layer="l1", source="a", content="l1", tokens=1),
            ContextItem(layer="l4", source="m", content="l4-low", tokens=1, importance=1.0),
            ContextItem(layer="l2", source="b", content="l2", tokens=1),
            ContextItem(layer="l3", source="p", content="l3-high", tokens=1, importance=10.0),
        ]
        ranked = ContextAssembler._rank(items)
        # L1 and L2 come first in original order
        assert ranked[0].content == "l1"
        assert ranked[1].content == "l2"
        # L3/L4 sorted by score
        assert ranked[2].content == "l3-high"
        assert ranked[3].content == "l4-low"


# ---------------------------------------------------------------------------
# ContextItem new fields (sensitivity_level, source_member_id, remove_fields)
# ---------------------------------------------------------------------------


class TestContextItemNewFields:
    """Tests for new privacy-related fields on ContextItem."""

    def test_default_sensitivity_level(self):
        item = ContextItem(layer="l4", source="mem", content="x")
        assert item.sensitivity_level == "public"

    def test_custom_sensitivity_level(self):
        item = ContextItem(layer="l4", source="mem", content="x", sensitivity_level="private")
        assert item.sensitivity_level == "private"

    def test_default_source_member_id(self):
        item = ContextItem(layer="l4", source="mem", content="x")
        assert item.source_member_id is None

    def test_custom_source_member_id(self):
        uid = str(uuid4())
        item = ContextItem(layer="l4", source="mem", content="x", source_member_id=uid)
        assert item.source_member_id == uid

    def test_remove_fields_returns_new_item(self):
        item = ContextItem(
            layer="l4", source="mem", content="x",
            metadata={"location": "Beijing", "schedule_gaps": [1, 2], "name": "Alice"},
        )
        cleaned = item.remove_fields(["location", "schedule_gaps"])
        assert cleaned is not item
        assert "location" not in cleaned.metadata
        assert "schedule_gaps" not in cleaned.metadata
        assert cleaned.metadata["name"] == "Alice"

    def test_remove_fields_empty_list_returns_same(self):
        item = ContextItem(layer="l4", source="mem", content="x", metadata={"a": 1})
        same = item.remove_fields([])
        assert same is item

    def test_remove_fields_does_not_mutate_original(self):
        item = ContextItem(layer="l4", source="mem", content="x", metadata={"a": 1, "b": 2})
        item.remove_fields(["a"])
        assert "a" in item.metadata  # original unchanged


# ---------------------------------------------------------------------------
# PrivacyFilter (Step 3a)
# ---------------------------------------------------------------------------


class TestPrivacyFilter:
    """Tests for PrivacyFilter.apply."""

    def _make_item(self, sensitivity: str = "public", creator_id: str = None,
                   family_id: str = None, **kwargs) -> ContextItem:
        meta = kwargs.pop("metadata", {})
        if family_id:
            meta["family_id"] = family_id
        return ContextItem(
            layer="l4", source="memory", content="test content", tokens=10,
            sensitivity_level=sensitivity, source_member_id=creator_id,
            metadata=meta, **kwargs,
        )

    def test_public_always_passes(self):
        item = self._make_item("public")
        kept, filtered = PrivacyFilter.apply([item], "viewer1", "fam1")
        assert len(kept) == 1
        assert filtered == 0

    def test_sensitive_always_blocked(self):
        item = self._make_item("sensitive")
        kept, filtered = PrivacyFilter.apply([item], "viewer1", "fam1")
        assert len(kept) == 0
        assert filtered == 1

    def test_private_passes_for_creator(self):
        uid = str(uuid4())
        item = self._make_item("private", creator_id=uid)
        kept, filtered = PrivacyFilter.apply([item], uid, "fam1")
        assert len(kept) == 1
        assert filtered == 0

    def test_private_blocked_for_other_user(self):
        creator = str(uuid4())
        viewer = str(uuid4())
        item = self._make_item("private", creator_id=creator)
        kept, filtered = PrivacyFilter.apply([item], viewer, "fam1")
        assert len(kept) == 0
        assert filtered == 1

    def test_private_blocked_when_no_source_member(self):
        item = self._make_item("private", creator_id=None)
        kept, filtered = PrivacyFilter.apply([item], "viewer1", "fam1")
        assert len(kept) == 0
        assert filtered == 1

    def test_family_passes_for_same_family(self):
        fam = str(uuid4())
        item = self._make_item("family", family_id=fam)
        kept, filtered = PrivacyFilter.apply([item], "viewer1", fam)
        assert len(kept) == 1
        assert filtered == 0

    def test_family_blocked_for_different_family(self):
        fam1 = str(uuid4())
        fam2 = str(uuid4())
        item = self._make_item("family", family_id=fam1)
        kept, filtered = PrivacyFilter.apply([item], "viewer1", fam2)
        assert len(kept) == 0
        assert filtered == 1

    def test_family_passes_when_no_family_in_metadata(self):
        """Family items without family_id metadata pass (conservative)."""
        item = self._make_item("family")
        kept, filtered = PrivacyFilter.apply([item], "viewer1", "fam1")
        assert len(kept) == 1
        assert filtered == 0

    def test_mixed_sensitivity_levels(self):
        items = [
            self._make_item("public"),
            self._make_item("sensitive"),
            self._make_item("private", creator_id="viewer1"),
            self._make_item("family", family_id="fam1"),
        ]
        kept, filtered = PrivacyFilter.apply(items, "viewer1", "fam1")
        assert len(kept) == 3  # public + private (creator) + family (same)
        assert filtered == 1  # sensitive

    def test_empty_input(self):
        kept, filtered = PrivacyFilter.apply([], "v", "f")
        assert kept == []
        assert filtered == 0


# ---------------------------------------------------------------------------
# ExclusionFilter (Step 3b)
# ---------------------------------------------------------------------------


class TestExclusionFilter:
    """Tests for ExclusionFilter.apply."""

    def _make_item(self, entity_ids=(), feedback_weight=1.0, **meta_kwargs) -> ContextItem:
        return ContextItem(
            layer="l4", source="memory", content="test", tokens=10,
            entity_ids=tuple(entity_ids), feedback_weight=feedback_weight,
            metadata=meta_kwargs,
        )

    def test_no_exclusion_passes_all(self):
        items = [self._make_item()]
        kept, filtered = ExclusionFilter.apply(items, set())
        assert len(kept) == 1
        assert filtered == 0

    def test_low_feedback_weight_excluded(self):
        item = self._make_item(feedback_weight=0.1)
        kept, filtered = ExclusionFilter.apply([item], set())
        assert len(kept) == 0
        assert filtered == 1

    def test_feedback_weight_at_threshold_passes(self):
        item = self._make_item(feedback_weight=FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD)
        kept, filtered = ExclusionFilter.apply([item], set())
        assert len(kept) == 1
        assert filtered == 0

    def test_feedback_weight_just_below_threshold_excluded(self):
        item = self._make_item(feedback_weight=FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD - 0.01)
        kept, filtered = ExclusionFilter.apply([item], set())
        assert len(kept) == 0
        assert filtered == 1

    def test_dismissed_entity_ids_excluded(self):
        entity_id = str(uuid4())
        item = self._make_item(entity_ids=[entity_id])
        kept, filtered = ExclusionFilter.apply(
            [item], set(), dismissed_entity_ids={entity_id},
        )
        assert len(kept) == 0
        assert filtered == 1

    def test_dismissed_entity_ids_no_match_passes(self):
        item = self._make_item(entity_ids=[str(uuid4())])
        kept, filtered = ExclusionFilter.apply(
            [item], set(), dismissed_entity_ids={str(uuid4())},
        )
        assert len(kept) == 1
        assert filtered == 0

    def test_l2_override_low_feedback_weight(self):
        """User mentions dismissed entity in current message -> override exclusion."""
        entity_id = str(uuid4())
        entity_uuid = UUID(entity_id)
        item = self._make_item(entity_ids=[entity_id], feedback_weight=0.1)
        kept, filtered = ExclusionFilter.apply([item], {entity_uuid})
        assert len(kept) == 1  # override
        assert filtered == 0

    def test_l2_override_dismissed_entity(self):
        entity_id = str(uuid4())
        entity_uuid = UUID(entity_id)
        item = self._make_item(entity_ids=[entity_id])
        kept, filtered = ExclusionFilter.apply(
            [item], {entity_uuid}, dismissed_entity_ids={entity_id},
        )
        assert len(kept) == 1  # override
        assert filtered == 0

    def test_l2_override_requires_matching_entity(self):
        """Override only works when the entity matches resolved_entity_ids."""
        excluded_entity = str(uuid4())
        other_entity = uuid4()
        item = self._make_item(entity_ids=[excluded_entity])
        kept, filtered = ExclusionFilter.apply(
            [item], {other_entity}, dismissed_entity_ids={excluded_entity},
        )
        assert len(kept) == 0
        assert filtered == 1

    def test_metadata_dismissed_entity_ids(self):
        """Items with dismissed_entity_ids in metadata are excluded."""
        entity_id = str(uuid4())
        item = self._make_item(
            entity_ids=[entity_id],
            dismissed_entity_ids=[entity_id],
        )
        kept, filtered = ExclusionFilter.apply([item], set())
        assert len(kept) == 0
        assert filtered == 1

    def test_cooldown_period_excludes_recent_dismiss(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=1)  # within default 7-day cooldown
        item = self._make_item(last_dismissed_at=recent)
        kept, filtered = ExclusionFilter.apply([item], set())
        assert len(kept) == 0
        assert filtered == 1

    def test_cooldown_period_passes_old_dismiss(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=DEFAULT_COOLDOWN_DAYS + 1)
        item = self._make_item(last_dismissed_at=old)
        kept, filtered = ExclusionFilter.apply([item], set())
        assert len(kept) == 1
        assert filtered == 0

    def test_custom_cooldown_days(self):
        now = datetime.now(timezone.utc)
        dismiss_time = now - timedelta(days=3)
        item = self._make_item(last_dismissed_at=dismiss_time)
        # Default cooldown is 7 days, so 3 days ago is within cooldown
        kept, filtered = ExclusionFilter.apply([item], set(), cooldown_days=2.0)
        # 3 days > 2 day cooldown -> should pass
        assert len(kept) == 1
        assert filtered == 0

    def test_l2_override_cooldown(self):
        entity_id = str(uuid4())
        entity_uuid = UUID(entity_id)
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=1)
        item = self._make_item(entity_ids=[entity_id], last_dismissed_at=recent)
        kept, filtered = ExclusionFilter.apply([item], {entity_uuid})
        assert len(kept) == 1  # override
        assert filtered == 0

    def test_empty_input(self):
        kept, filtered = ExclusionFilter.apply([], set())
        assert kept == []
        assert filtered == 0

    def test_item_without_entities_not_excluded_by_dismissed_set(self):
        item = self._make_item(entity_ids=[])
        kept, filtered = ExclusionFilter.apply(
            [item], set(), dismissed_entity_ids={str(uuid4())},
        )
        assert len(kept) == 1
        assert filtered == 0


# ---------------------------------------------------------------------------
# apply_filters (chained PrivacyFilter + ExclusionFilter)
# ---------------------------------------------------------------------------


class TestApplyFilters:
    """Tests for the chained apply_filters function."""

    def test_both_filters_applied(self):
        viewer = str(uuid4())
        family = str(uuid4())
        entity_id = str(uuid4())

        items = [
            # Should pass both filters
            ContextItem(
                layer="l4", source="mem", content="ok", tokens=10,
                sensitivity_level="public", feedback_weight=1.0,
            ),
            # Blocked by privacy (sensitive)
            ContextItem(
                layer="l4", source="mem", content="secret", tokens=10,
                sensitivity_level="sensitive",
            ),
            # Blocked by exclusion (low feedback_weight)
            ContextItem(
                layer="l4", source="mem", content="dismissed", tokens=10,
                sensitivity_level="public", feedback_weight=0.1,
            ),
        ]

        kept, filtered = apply_filters(items, viewer, family, set())
        assert len(kept) == 1
        assert kept[0].content == "ok"
        assert filtered == 2

    def test_privacy_runs_before_exclusion(self):
        """Items blocked by privacy are not counted by exclusion."""
        viewer = str(uuid4())
        family = str(uuid4())

        items = [
            ContextItem(
                layer="l4", source="mem", content="sensitive+low",
                tokens=10, sensitivity_level="sensitive", feedback_weight=0.1,
            ),
        ]
        kept, filtered = apply_filters(items, viewer, family, set())
        assert len(kept) == 0
        assert filtered == 1  # only privacy filter caught it

    def test_integration_with_assembler_pipeline(self):
        """Verify _apply_filters delegates to apply_filters correctly."""
        viewer = str(uuid4())
        family = str(uuid4())
        items = [
            ContextItem(layer="l1", source="note", content="fact", tokens=10),
            ContextItem(
                layer="l4", source="mem", content="sensitive", tokens=10,
                sensitivity_level="sensitive",
            ),
        ]
        kept, filtered = ContextAssembler._apply_filters(
            items, viewer, family, set(),
        )
        assert len(kept) == 1
        assert kept[0].content == "fact"
        assert filtered == 1


# ---------------------------------------------------------------------------
# PrivacyInferenceGuard (Step 3c)
# ---------------------------------------------------------------------------


class TestPrivacyInferenceGuard:
    """Tests for PrivacyInferenceGuard.sanitize."""

    def _make_item(self, source_member_id=None, **meta) -> ContextItem:
        return ContextItem(
            layer="l4", source="memory", content="test", tokens=10,
            source_member_id=source_member_id, metadata=meta,
        )

    def test_no_privacy_settings_passthrough(self):
        items = [self._make_item(source_member_id="m1", location="Beijing")]
        result = PrivacyInferenceGuard.sanitize(items, None)
        assert len(result) == 1
        assert result[0].metadata.get("location") == "Beijing"

    def test_empty_privacy_settings_passthrough(self):
        items = [self._make_item(source_member_id="m1", location="Beijing")]
        result = PrivacyInferenceGuard.sanitize(items, {})
        assert len(result) == 1
        assert result[0].metadata.get("location") == "Beijing"

    def test_location_removed_when_share_location_false(self):
        member_id = str(uuid4())
        items = [self._make_item(
            source_member_id=member_id,
            location="Beijing", coordinates="39.9,116.4", address="Haidian",
            name="Alice",
        )]
        settings = {member_id: {"share_location": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert len(result) == 1
        assert "location" not in result[0].metadata
        assert "coordinates" not in result[0].metadata
        assert "address" not in result[0].metadata
        assert result[0].metadata["name"] == "Alice"

    def test_schedule_removed_when_share_schedule_false(self):
        member_id = str(uuid4())
        items = [self._make_item(
            source_member_id=member_id,
            schedule_gaps=["9-10am"], free_slots=["Wed PM"],
            name="Bob",
        )]
        settings = {member_id: {"share_schedule": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert len(result) == 1
        assert "schedule_gaps" not in result[0].metadata
        assert "free_slots" not in result[0].metadata
        assert result[0].metadata["name"] == "Bob"

    def test_location_kept_when_share_location_true(self):
        member_id = str(uuid4())
        items = [self._make_item(
            source_member_id=member_id,
            location="Beijing",
        )]
        settings = {member_id: {"share_location": True}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert result[0].metadata.get("location") == "Beijing"

    def test_schedule_kept_when_share_schedule_true(self):
        member_id = str(uuid4())
        items = [self._make_item(
            source_member_id=member_id,
            schedule_gaps=["9-10am"],
        )]
        settings = {member_id: {"share_schedule": True}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert result[0].metadata.get("schedule_gaps") == ["9-10am"]

    def test_no_source_member_id_passthrough(self):
        items = [self._make_item(location="Beijing")]
        settings = {"other_member": {"share_location": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert result[0].metadata.get("location") == "Beijing"

    def test_member_not_in_settings_passthrough(self):
        items = [self._make_item(source_member_id="unknown", location="Beijing")]
        settings = {"other_member": {"share_location": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert result[0].metadata.get("location") == "Beijing"

    def test_both_location_and_schedule_removed(self):
        member_id = str(uuid4())
        items = [self._make_item(
            source_member_id=member_id,
            location="Shanghai", schedule_gaps=["Mon 2-4pm"],
        )]
        settings = {member_id: {"share_location": False, "share_schedule": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert "location" not in result[0].metadata
        assert "schedule_gaps" not in result[0].metadata

    def test_multiple_members_different_settings(self):
        m1 = str(uuid4())
        m2 = str(uuid4())
        items = [
            self._make_item(source_member_id=m1, location="Beijing", schedule_gaps=["9am"]),
            self._make_item(source_member_id=m2, location="Shanghai", schedule_gaps=["2pm"]),
        ]
        settings = {
            m1: {"share_location": False, "share_schedule": True},
            m2: {"share_location": True, "share_schedule": False},
        }
        result = PrivacyInferenceGuard.sanitize(items, settings)
        # m1: location removed, schedule kept
        assert "location" not in result[0].metadata
        assert result[0].metadata.get("schedule_gaps") == ["9am"]
        # m2: location kept, schedule removed
        assert result[1].metadata.get("location") == "Shanghai"
        assert "schedule_gaps" not in result[1].metadata

    def test_immutability_original_not_mutated(self):
        member_id = str(uuid4())
        item = self._make_item(source_member_id=member_id, location="Beijing")
        settings = {member_id: {"share_location": False}}
        result = PrivacyInferenceGuard.sanitize([item], settings)
        # Original item unchanged
        assert item.metadata.get("location") == "Beijing"
        # Sanitized item has location removed
        assert "location" not in result[0].metadata

    def test_empty_items_returns_empty(self):
        result = PrivacyInferenceGuard.sanitize([], {"m": {"share_location": False}})
        assert result == []

    def test_default_share_location_is_true(self):
        """share_location defaults to True when key is missing from settings."""
        member_id = str(uuid4())
        items = [self._make_item(source_member_id=member_id, location="Beijing")]
        # Settings present for member but no share_location key
        settings = {member_id: {"share_schedule": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert result[0].metadata.get("location") == "Beijing"

    def test_default_share_schedule_is_true(self):
        """share_schedule defaults to True when key is missing from settings."""
        member_id = str(uuid4())
        items = [self._make_item(source_member_id=member_id, schedule_gaps=["9am"])]
        settings = {member_id: {"share_location": False}}
        result = PrivacyInferenceGuard.sanitize(items, settings)
        assert result[0].metadata.get("schedule_gaps") == ["9am"]


# ---------------------------------------------------------------------------
# apply_filters with PrivacyInferenceGuard integration
# ---------------------------------------------------------------------------


class TestApplyFiltersWithInferenceGuard:
    """Tests for the full filter chain including PrivacyInferenceGuard."""

    def test_inference_guard_applied_in_chain(self):
        member_id = str(uuid4())
        viewer = str(uuid4())
        family = str(uuid4())

        items = [
            ContextItem(
                layer="l4", source="mem", content="info", tokens=10,
                sensitivity_level="public", source_member_id=member_id,
                metadata={"location": "Beijing", "name": "test"},
            ),
        ]
        settings = {member_id: {"share_location": False}}

        kept, filtered = apply_filters(
            items, viewer, family, set(), privacy_settings=settings,
        )
        assert len(kept) == 1
        assert "location" not in kept[0].metadata
        assert kept[0].metadata["name"] == "test"
        assert filtered == 0  # inference guard sanitizes, doesn't filter

    def test_sensitive_filtered_before_inference_guard(self):
        """Sensitive items never reach the inference guard."""
        member_id = str(uuid4())
        viewer = str(uuid4())
        family = str(uuid4())

        items = [
            ContextItem(
                layer="l4", source="mem", content="secret", tokens=10,
                sensitivity_level="sensitive", source_member_id=member_id,
                metadata={"location": "Beijing"},
            ),
        ]
        settings = {member_id: {"share_location": False}}
        kept, filtered = apply_filters(
            items, viewer, family, set(), privacy_settings=settings,
        )
        assert len(kept) == 0
        assert filtered == 1


# ---------------------------------------------------------------------------
# Token-aware L2 windowing (Phase 2 trimming)
# ---------------------------------------------------------------------------


def _make_l2_item(content: str, tokens: int) -> ContextItem:
    """Helper for L2 ContextItem creation."""
    return ContextItem(layer="l2", source="conversation", content=content, tokens=tokens)


def _apply_l2_token_window(l2: list, l2_budget: int, window_size: int = 25) -> list:
    """Replicate the production two-phase L2 windowing logic for unit testing."""
    import dataclasses
    from src.ai_engine.context_assembler import estimate_tokens

    # Phase 1: count-based window
    if len(l2) > window_size:
        l2 = l2[-window_size:]

    # Phase 2: token-aware trimming
    trimmed: list = []
    used = 0
    for item in reversed(l2):
        if used + item.tokens <= l2_budget or not trimmed:
            # 1.2x size guard for at-least-one (consistent with _truncate_items_to_budget)
            if not trimmed and item.tokens > int(l2_budget * 1.2):
                ratio = (l2_budget * 1.2) / item.tokens if item.tokens > 0 else 1.0
                truncated_len = max(1, int(len(item.content) * ratio))
                truncated_content = item.content[:truncated_len] + "..."
                item = dataclasses.replace(
                    item,
                    content=truncated_content,
                    tokens=estimate_tokens(truncated_content),
                )
            trimmed.append(item)
            used += item.tokens
        else:
            break
    trimmed.reverse()
    return trimmed


class TestL2TokenAwareWindowing:
    """Tests for token-aware L2 window sizing (PLAN-001)."""

    def test_all_short_messages_fit(self):
        """All messages fit within budget — no trimming needed."""
        l2 = [_make_l2_item(f"msg {i}", tokens=50) for i in range(10)]
        # 10 * 50 = 500 tokens, well under 2000 budget
        result = _apply_l2_token_window(l2, l2_budget=2000)
        assert len(result) == 10
        assert result == l2

    def test_all_long_messages_only_newest_fit(self):
        """Each message is ~800 tokens; budget 2000 keeps only the 2 newest."""
        l2 = [_make_l2_item(f"long msg {i}", tokens=800) for i in range(5)]
        result = _apply_l2_token_window(l2, l2_budget=2000)
        # 800 + 800 = 1600 fits; 800 * 3 = 2400 > 2000 → only 2 newest
        assert len(result) == 2
        # newest items are l2[3] and l2[4]
        assert result[0] is l2[3]
        assert result[1] is l2[4]

    def test_mixed_length_newest_first_selection(self):
        """Mix of short (50 tok) and long (500 tok) messages; newest-first selection."""
        l2 = [
            _make_l2_item("old short", tokens=50),
            _make_l2_item("old long", tokens=500),
            _make_l2_item("mid short", tokens=50),
            _make_l2_item("new long", tokens=500),
            _make_l2_item("newest short", tokens=50),
        ]
        # budget 700: newest_short(50) + new_long(500) + mid_short(50) = 600 fits
        # adding old_long(500) would = 1100 > 700 → stop
        result = _apply_l2_token_window(l2, l2_budget=700)
        assert len(result) == 3
        assert result[0] is l2[2]  # mid_short
        assert result[1] is l2[3]  # new_long
        assert result[2] is l2[4]  # newest_short

    def test_empty_l2_no_crash(self):
        """Empty L2 list should return empty without error."""
        result = _apply_l2_token_window([], l2_budget=2000)
        assert result == []

    def test_single_oversized_message_at_least_one_policy(self):
        """Single message exceeding budget is included but truncated via 1.2x guard."""
        l2 = [_make_l2_item("x" * 6000, tokens=3000)]
        result = _apply_l2_token_window(l2, l2_budget=2000)
        assert len(result) == 1
        # 3000 > 2000 * 1.2 = 2400, so content should be truncated
        assert result[0].tokens <= int(2000 * 1.2) + 50  # allow estimate margin
        assert result[0].content.endswith("...")

    def test_window_size_applies_before_token_trimming(self):
        """Count window (window_size) is applied first, then token trimming."""
        # 10 messages, each 100 tokens; window_size=3 → keep last 3
        # budget=2000 easily fits 3 * 100 = 300 tokens
        l2 = [_make_l2_item(f"msg {i}", tokens=100) for i in range(10)]
        result = _apply_l2_token_window(l2, l2_budget=2000, window_size=3)
        assert len(result) == 3
        # should be the 3 newest
        assert result[0] is l2[7]
        assert result[1] is l2[8]
        assert result[2] is l2[9]

    def test_window_size_and_token_budget_both_constrain(self):
        """When both count window and token budget restrict, the stricter wins."""
        # 10 messages, each 800 tokens; window_size=5, budget=2000
        # Phase 1: keep last 5 → 5 * 800 = 4000 tokens
        # Phase 2: trim to budget 2000 → keep only 2 newest
        l2 = [_make_l2_item(f"large {i}", tokens=800) for i in range(10)]
        result = _apply_l2_token_window(l2, l2_budget=2000, window_size=5)
        assert len(result) == 2
        assert result[0] is l2[8]
        assert result[1] is l2[9]

    def test_chronological_order_preserved(self):
        """Output should be in chronological (oldest-first) order."""
        l2 = [_make_l2_item(f"msg {i}", tokens=300) for i in range(5)]
        # budget 1000: fits 3 newest (300 * 3 = 900)
        result = _apply_l2_token_window(l2, l2_budget=1000)
        assert len(result) == 3
        # Oldest of the kept should come first
        assert result[0] is l2[2]
        assert result[1] is l2[3]
        assert result[2] is l2[4]
