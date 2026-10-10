"""Unit tests for insight quality optimizations.

Tests the pipeline dedup key computation and kanban holiday dedup logic.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.insight.models import EntitySpec, InsightCandidate, InsightType
from src.modules.views.services.kanban_service import KanbanService


# ---------------------------------------------------------------
# InsightPipeline._compute_dedup_key (obligation-identity based)
# ---------------------------------------------------------------


def _pipeline():
    from src.modules.insight.insight_pipeline import InsightPipeline
    return InsightPipeline(AsyncMock())


class TestPipelineDedupKey:
    """Verify that _compute_dedup_key produces obligation-identity-based keys."""

    def test_same_important_date_different_titles(self):
        """Same important_date entity → same dedup key regardless of title."""
        p = _pipeline()
        idate_id = str(uuid4())

        key_a = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.TIME.value,
            title="龙抬头快到了",
            content="6天后是龙抬头",
            entities=[EntitySpec(entity_type="important_date", entity_id=idate_id, role="primary")],
        ))
        key_b = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.TIME.value,
            title="龙抬头（3月1日）快到了，记得为家人准备",
            content="记得准备",
            entities=[EntitySpec(entity_type="important_date", entity_id=idate_id, role="primary")],
        ))
        assert key_a == key_b

    def test_different_important_dates_different_keys(self):
        """Different important_date entities → different keys."""
        p = _pipeline()

        key_a = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.TIME.value,
            title="龙抬头快到了",
            content="6天后是龙抬头",
            entities=[EntitySpec(entity_type="important_date", entity_id=str(uuid4()), role="primary")],
        ))
        key_b = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.TIME.value,
            title="元宵节快到了",
            content="3天后是元宵节",
            entities=[EntitySpec(entity_type="important_date", entity_id=str(uuid4()), role="primary")],
        ))
        assert key_a != key_b

    def test_same_person_different_titles(self):
        """Same person entity → same relationship key."""
        p = _pipeline()
        person_id = str(uuid4())

        key_a = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.RELATIONSHIP.value,
            title="别忘了联系李明",
            content="已经2周没联系",
            entities=[EntitySpec(entity_type="person", entity_id=person_id, role="primary")],
        ))
        key_b = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.RELATIONSHIP.value,
            title="去杭州记得找李明",
            content="可以见面",
            entities=[EntitySpec(entity_type="person", entity_id=person_id, role="primary")],
        ))
        assert key_a == key_b

    def test_favor_dedup_by_source_entity(self):
        """Favor dedup key uses source favor entity ID."""
        p = _pipeline()
        favor_id = str(uuid4())

        key_a = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.FAVOR.value,
            title="答谢提醒",
            content="记得感谢小明帮忙",
            entities=[EntitySpec(entity_type="favor", entity_id=favor_id, role="source")],
        ))
        key_b = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.FAVOR.value,
            title="回礼提醒",
            content="还没回礼",
            entities=[EntitySpec(entity_type="favor", entity_id=favor_id, role="source")],
        ))
        assert key_a == key_b
        assert key_a == f"favor:{favor_id}"

    def test_commitment_dedup_by_source_entity(self):
        """Commitment dedup key uses source commitment entity ID."""
        p = _pipeline()
        cid = str(uuid4())

        key = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.EFFICIENCY.value,
            title="承诺提醒",
            content="明天截止",
            entities=[EntitySpec(entity_type="commitment", entity_id=cid, role="source")],
        ))
        assert key == f"commitment:{cid}"

    def test_fallback_uses_content_hash(self):
        """Without entities, falls back to content-based hash."""
        p = _pipeline()

        key = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.EFFICIENCY.value,
            title="测试标题",
            content="测试内容",
        ))
        assert key.startswith("efficiency:")
        assert len(key) > len("efficiency:")

    def test_same_important_date_with_source_context(self):
        """Source context important_date_id is used as fallback."""
        p = _pipeline()
        date_id = str(uuid4())

        key_a = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.TIME.value,
            title="6天后是龙抬头",
            content="记得准备",
            source_context={"important_date_id": date_id},
        ))
        key_b = p._compute_dedup_key(InsightCandidate(
            insight_type=InsightType.TIME.value,
            title="龙抬头准备提醒",
            content="快到了",
            source_context={"important_date_id": date_id},
        ))
        assert key_a == key_b


# ---------------------------------------------------------------
# KanbanService._insight_dedup_key
# ---------------------------------------------------------------


class TestKanbanInsightDedupKey:
    """Verify that kanban dedup keys handle holiday/important_date entities."""

    def test_holiday_key(self):
        """Same holiday in action_data → same key."""
        insight = SimpleNamespace(
            id="a",
            insight_type="reminder",
            action_data={"holiday": "龙抬头"},
        )
        key = KanbanService._insight_dedup_key(insight)
        assert key == ("holiday", "龙抬头")

    def test_important_date_key(self):
        """Important date type → keyed by person_name."""
        insight = SimpleNamespace(
            id="b",
            insight_type="time",
            action_data={"type": "important_date", "person_name": "妈妈"},
        )
        key = KanbanService._insight_dedup_key(insight)
        assert key == ("important_date", "妈妈", "time")

    def test_person_key_unchanged(self):
        """Person key still works as before."""
        insight = SimpleNamespace(
            id="c",
            insight_type="relationship",
            action_data={"person": "李明"},
        )
        key = KanbanService._insight_dedup_key(insight)
        assert key == ("李明", "relationship")

    def test_fallback_key_unchanged(self):
        """Non-entity insights still fall back to (type, id)."""
        insight = SimpleNamespace(
            id="d",
            insight_type="general",
            action_data={},
        )
        key = KanbanService._insight_dedup_key(insight)
        assert key == ("general", "d")

    def test_missing_action_data(self):
        """Missing action_data should not raise."""
        insight = SimpleNamespace(
            id="e",
            insight_type="reminder",
        )
        key = KanbanService._insight_dedup_key(insight)
        assert isinstance(key, tuple)
