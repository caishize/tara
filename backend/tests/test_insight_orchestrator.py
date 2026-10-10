"""Tests for the unified insight system (pipeline + domain bridge).

Covers:
- InsightPipeline._compute_dedup_key (obligation-identity dedup)
- InsightDomainBridge lifecycle event handling
- InsightCandidate / EntitySpec dataclass behavior
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.insight.models import EntitySpec, InsightCandidate, InsightType


# ------------------------------------------------------------------
# Dedup key computation tests
# ------------------------------------------------------------------


def _make_pipeline(db=None):
    """Create a minimal InsightPipeline for unit testing."""
    from src.modules.insight.insight_pipeline import InsightPipeline

    return InsightPipeline(db or AsyncMock())


def test_dedup_key_favor_uses_source_entity():
    """Favor dedup key is favor:{favor_record_id} via source entity."""
    pipeline = _make_pipeline()
    favor_id = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="答谢提醒",
        content="记得感谢小明帮忙",
        entities=[
            EntitySpec(entity_type="favor", entity_id=favor_id, role="source"),
            EntitySpec(entity_type="person", entity_id=str(uuid4()), role="primary"),
        ],
    )

    key = pipeline._compute_dedup_key(candidate)
    assert key == f"favor:{favor_id}"


def test_dedup_key_favor_falls_back_to_source_context():
    """Favor dedup key uses source_context.favor_record_id as fallback."""
    pipeline = _make_pipeline()
    favor_id = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="答谢提醒",
        content="记得感谢小明帮忙",
        source_context={"favor_record_id": favor_id},
    )

    key = pipeline._compute_dedup_key(candidate)
    assert key == f"favor:{favor_id}"


def test_dedup_key_relationship_uses_primary_person():
    """Relationship dedup key is relationship:{person_id} via primary person entity."""
    pipeline = _make_pipeline()
    person_id = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="好久没联系小明了",
        content="已经2周没有联系了",
        entities=[
            EntitySpec(entity_type="person", entity_id=person_id, role="primary"),
        ],
    )

    key = pipeline._compute_dedup_key(candidate)
    assert key == f"relationship:{person_id}"


def test_dedup_same_person_same_key():
    """Two relationship insights for same person produce identical dedup keys."""
    pipeline = _make_pipeline()
    person_id = str(uuid4())

    key1 = pipeline._compute_dedup_key(InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="好久没联系小明了",
        content="已经2周没有联系了",
        entities=[EntitySpec(entity_type="person", entity_id=person_id, role="primary")],
    ))
    key2 = pipeline._compute_dedup_key(InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="记得联系小明",
        content="可以打个电话",
        entities=[EntitySpec(entity_type="person", entity_id=person_id, role="primary")],
    ))

    assert key1 == key2


def test_dedup_different_person_different_key():
    """Two relationship insights for different persons produce different keys."""
    pipeline = _make_pipeline()

    key_a = pipeline._compute_dedup_key(InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="好久没联系小明了",
        content="已经2周没有联系了",
        entities=[EntitySpec(entity_type="person", entity_id=str(uuid4()), role="primary")],
    ))
    key_b = pipeline._compute_dedup_key(InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="好久没联系小红了",
        content="已经3周没有联系了",
        entities=[EntitySpec(entity_type="person", entity_id=str(uuid4()), role="primary")],
    ))

    assert key_a != key_b


def test_dedup_key_commitment_uses_source_entity():
    """Commitment dedup key is commitment:{commitment_id} via source entity."""
    pipeline = _make_pipeline()
    commitment_id = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.EFFICIENCY.value,
        title="承诺提醒",
        content="明天要完成的承诺",
        entities=[
            EntitySpec(entity_type="commitment", entity_id=commitment_id, role="source"),
        ],
    )

    key = pipeline._compute_dedup_key(candidate)
    assert key == f"commitment:{commitment_id}"


def test_dedup_key_time_uses_important_date_and_event():
    """Time dedup key is time:{important_date_id}:{event_id}."""
    pipeline = _make_pipeline()
    idate_id = str(uuid4())
    event_id = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.TIME.value,
        title="龙抬头快到了",
        content="6天后是龙抬头",
        entities=[
            EntitySpec(entity_type="important_date", entity_id=idate_id, role="primary"),
            EntitySpec(entity_type="event", entity_id=event_id, role="related"),
        ],
    )

    key = pipeline._compute_dedup_key(candidate)
    assert key == f"time:{idate_id}:{event_id}"


def test_dedup_key_trip_single_entity_uses_trip_id():
    """Single trip entity produces trip-scoped dedup key to prevent
    near-duplicate insights from different events of the same trip."""
    pipeline = _make_pipeline()
    trip_id = str(uuid4())
    event_id = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.TIME.value,
        title="深圳游准备",
        content="记得订好返程票和住宿",
        entities=[
            EntitySpec(entity_type="trip", entity_id=trip_id, role="related"),
            EntitySpec(entity_type="event", entity_id=event_id, role="related"),
        ],
    )

    key = pipeline._compute_dedup_key(candidate)
    assert key == f"trip:{trip_id}:time"


def test_dedup_key_fallback_uses_type_and_entity_ids():
    """Fallback dedup key uses type + sorted entity IDs (multi-trip case)."""
    pipeline = _make_pipeline()
    eid1 = str(uuid4())
    eid2 = str(uuid4())

    candidate = InsightCandidate(
        insight_type=InsightType.EFFICIENCY.value,
        title="效率建议",
        content="可以优化日程",
        entities=[
            EntitySpec(entity_type="trip", entity_id=eid1, role="related"),
            EntitySpec(entity_type="trip", entity_id=eid2, role="related"),
        ],
    )

    key = pipeline._compute_dedup_key(candidate)
    expected_ids = ",".join(sorted([eid1, eid2]))
    assert key == f"efficiency:{expected_ids}"


# ------------------------------------------------------------------
# Cross-candidate overlap dedup tests
# ------------------------------------------------------------------


def test_cross_candidate_dedup_drops_subset_favor():
    """Individual favor insight is dropped when a combined insight covers the same person."""
    pipeline = _make_pipeline()
    elena_id = str(uuid4())
    grandma_id = str(uuid4())

    # Individual insight: only Elena
    individual = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="Elena大额人情",
        content="Elena给了1万元，记得回礼",
        entities=[
            EntitySpec(entity_type="person", entity_id=elena_id, role="primary"),
        ],
    )

    # Combined insight: Elena + grandma
    combined = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="大额人情待还",
        content="外婆和Elena分别给了1000和10000元",
        entities=[
            EntitySpec(entity_type="person", entity_id=elena_id, role="primary"),
            EntitySpec(entity_type="person", entity_id=grandma_id, role="related"),
        ],
    )

    result = pipeline._cross_candidate_dedup([individual, combined])
    assert len(result) == 1
    assert result[0].title == "大额人情待还"


def test_cross_candidate_dedup_keeps_non_overlapping():
    """Two favor insights about different people are both kept."""
    pipeline = _make_pipeline()
    person_a = str(uuid4())
    person_b = str(uuid4())

    insight_a = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="A的人情",
        content="A给了5000元",
        entities=[EntitySpec(entity_type="person", entity_id=person_a, role="primary")],
    )
    insight_b = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="B的人情",
        content="B给了3000元",
        entities=[EntitySpec(entity_type="person", entity_id=person_b, role="primary")],
    )

    result = pipeline._cross_candidate_dedup([insight_a, insight_b])
    assert len(result) == 2


def test_cross_candidate_dedup_ignores_non_favor_types():
    """Non-favor/relationship insights are not affected by cross-candidate dedup."""
    pipeline = _make_pipeline()
    person_id = str(uuid4())

    time_insight = InsightCandidate(
        insight_type=InsightType.TIME.value,
        title="生日提醒",
        content="明天是生日",
        entities=[EntitySpec(entity_type="person", entity_id=person_id, role="primary")],
    )
    favor_insight = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="人情提醒",
        content="记得回礼",
        entities=[
            EntitySpec(entity_type="person", entity_id=person_id, role="primary"),
            EntitySpec(entity_type="person", entity_id=str(uuid4()), role="related"),
        ],
    )

    result = pipeline._cross_candidate_dedup([time_insight, favor_insight])
    assert len(result) == 2


def test_cross_candidate_dedup_relationship_type_also_deduped():
    """Relationship-type insights are also subject to cross-candidate dedup."""
    pipeline = _make_pipeline()
    elena_id = str(uuid4())
    grandma_id = str(uuid4())

    individual = InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="联系Elena",
        content="好久没联系了",
        entities=[EntitySpec(entity_type="person", entity_id=elena_id, role="primary")],
    )
    combined = InsightCandidate(
        insight_type=InsightType.RELATIONSHIP.value,
        title="联系亲人",
        content="外婆和Elena都好久没联系了",
        entities=[
            EntitySpec(entity_type="person", entity_id=elena_id, role="primary"),
            EntitySpec(entity_type="person", entity_id=grandma_id, role="related"),
        ],
    )

    result = pipeline._cross_candidate_dedup([individual, combined])
    assert len(result) == 1
    assert result[0].title == "联系亲人"


def test_cross_candidate_dedup_single_candidate_passthrough():
    """Single candidate passes through unchanged."""
    pipeline = _make_pipeline()
    candidate = InsightCandidate(
        insight_type=InsightType.FAVOR.value,
        title="人情提醒",
        content="记得回礼",
        entities=[EntitySpec(entity_type="person", entity_id=str(uuid4()), role="primary")],
    )
    result = pipeline._cross_candidate_dedup([candidate])
    assert len(result) == 1


# ------------------------------------------------------------------
# InsightCandidate / EntitySpec dataclass tests
# ------------------------------------------------------------------


def test_insight_candidate_person_ids_property():
    """InsightCandidate.person_ids extracts person entity IDs."""
    pid = str(uuid4())
    candidate = InsightCandidate(
        insight_type="relationship",
        title="Test",
        content="Test",
        entities=[
            EntitySpec(entity_type="person", entity_id=pid, role="primary"),
            EntitySpec(entity_type="event", entity_id=str(uuid4()), role="related"),
        ],
    )
    assert candidate.person_ids == [pid]


def test_insight_candidate_source_entity_ids_property():
    """InsightCandidate.source_entity_ids extracts source role IDs."""
    src_id = str(uuid4())
    candidate = InsightCandidate(
        insight_type="favor",
        title="Test",
        content="Test",
        entities=[
            EntitySpec(entity_type="favor", entity_id=src_id, role="source"),
            EntitySpec(entity_type="person", entity_id=str(uuid4()), role="primary"),
        ],
    )
    assert candidate.source_entity_ids == [src_id]


# ------------------------------------------------------------------
# InsightDomainBridge tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_domain_bridge_adopted_marks_favor_in_progress():
    """handle_insight_adopted marks favor as in_progress."""
    from src.modules.insight.insight_domain_bridge import (
        InsightAdoptedEntityRef,
        InsightAdoptedEvent,
        InsightDomainBridge,
    )

    db = AsyncMock()
    favor_id = uuid4()

    # Mock favor record
    mock_favor = MagicMock()
    mock_favor.status = "pending"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_favor
    db.execute.return_value = mock_result

    bridge = InsightDomainBridge(db)
    event = InsightAdoptedEvent(
        insight_id=uuid4(),
        insight_type="favor",
        user_id=uuid4(),
        family_id=uuid4(),
        entities=[
            InsightAdoptedEntityRef(entity_type="favor", entity_id=favor_id, role="source"),
        ],
    )

    await bridge.handle_insight_adopted(event)
    assert mock_favor.status == "in_progress"


@pytest.mark.asyncio
async def test_domain_bridge_adopted_records_interaction_intent():
    """handle_insight_adopted calls temperature_service for person entities."""
    from src.modules.insight.insight_domain_bridge import (
        InsightAdoptedEntityRef,
        InsightAdoptedEvent,
        InsightDomainBridge,
    )

    db = AsyncMock()
    person_id = uuid4()
    user_id = uuid4()

    mock_temp_svc = MagicMock()
    mock_temp_svc.record_interaction_intent = AsyncMock()

    bridge = InsightDomainBridge(db, temperature_service=mock_temp_svc)
    event = InsightAdoptedEvent(
        insight_id=uuid4(),
        insight_type="relationship",
        user_id=user_id,
        family_id=uuid4(),
        entities=[
            InsightAdoptedEntityRef(entity_type="person", entity_id=person_id, role="primary"),
        ],
    )

    await bridge.handle_insight_adopted(event)
    mock_temp_svc.record_interaction_intent.assert_called_once_with(
        person_id, interaction_type="insight_adopted",
    )


@pytest.mark.asyncio
async def test_domain_bridge_dismissed_cascades_to_ea():
    """handle_insight_dismissed calls ea_dismiss_fn for event_association entities."""
    from src.modules.insight.insight_domain_bridge import (
        InsightAdoptedEntityRef,
        InsightDismissedEvent,
        InsightDomainBridge,
    )

    db = AsyncMock()
    ea_id = uuid4()
    mock_ea_dismiss = AsyncMock()

    bridge = InsightDomainBridge(db, ea_dismiss_fn=mock_ea_dismiss)
    event = InsightDismissedEvent(
        insight_id=uuid4(),
        insight_type="time",
        user_id=uuid4(),
        family_id=uuid4(),
        permanent=True,
        entities=[
            InsightAdoptedEntityRef(entity_type="event_association", entity_id=ea_id, role="source"),
        ],
    )

    await bridge.handle_insight_dismissed(event)
    mock_ea_dismiss.assert_called_once_with(ea_id)


@pytest.mark.asyncio
async def test_domain_bridge_dismissed_permanent_field():
    """InsightDismissedEvent carries permanent flag."""
    from src.modules.insight.insight_domain_bridge import InsightDismissedEvent

    event = InsightDismissedEvent(
        insight_id=uuid4(),
        insight_type="time",
        user_id=uuid4(),
        family_id=uuid4(),
        permanent=True,
    )
    assert event.permanent is True

    event_soft = InsightDismissedEvent(
        insight_id=uuid4(),
        insight_type="time",
        user_id=uuid4(),
        family_id=uuid4(),
    )
    assert event_soft.permanent is False
