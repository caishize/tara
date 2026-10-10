"""Tests for GraphRAG recall methods in MemoryRecallService.

Covers:
- recall_graph_connected: single-hop, multi-hop, strength filter, SUPERSEDED filter
- recall_related_to_entity: entity matching, 1-hop expansion, ranking
"""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.memory.models import (
    ConversationMemory,
    MemoryAssociation,
    MemoryStatus,
)
from src.modules.memory.recall_service import MemoryRecallService
from src.core.utils.timezone import utc_now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(
    user_id,
    family_id,
    summary="test memory",
    importance=5,
    status=MemoryStatus.ACTIVE.value,
    entities=None,
    memory_type="general",
):
    return ConversationMemory(
        id=uuid4(),
        user_id=user_id,
        family_id=family_id,
        memory_type=memory_type,
        content="test content",
        summary=summary,
        importance=importance,
        confidence=0.8,
        status=status,
        sensitivity_level="public",
        entities=entities or {},
        tags=[],
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def _make_association(mem_a_id, mem_b_id, strength=0.5, assoc_type="related"):
    return MemoryAssociation(
        id=uuid4(),
        memory_id_a=mem_a_id,
        memory_id_b=mem_b_id,
        association_type=assoc_type,
        strength=strength,
        created_at=utc_now(),
    )


# ---------------------------------------------------------------------------
# recall_graph_connected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_hop_connected(db_session: AsyncSession):
    """Direct neighbours are returned at depth=1."""
    user_id = uuid4()
    family_id = uuid4()

    seed = _make_memory(user_id, family_id, summary="seed")
    neighbour = _make_memory(user_id, family_id, summary="neighbour")
    db_session.add_all([seed, neighbour])
    await db_session.flush()

    assoc = _make_association(seed.id, neighbour.id, strength=0.6)
    db_session.add(assoc)
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_graph_connected(seed.id, depth=1, min_strength=0.3)

    result_ids = {m.id for m in results}
    assert neighbour.id in result_ids
    assert seed.id not in result_ids, "Seed itself should not appear in results"


@pytest.mark.asyncio
async def test_multi_hop_connected(db_session: AsyncSession):
    """Two-hop traversal reaches memories connected transitively."""
    user_id = uuid4()
    family_id = uuid4()

    seed = _make_memory(user_id, family_id, summary="seed")
    hop1 = _make_memory(user_id, family_id, summary="hop1")
    hop2 = _make_memory(user_id, family_id, summary="hop2")
    db_session.add_all([seed, hop1, hop2])
    await db_session.flush()

    assoc1 = _make_association(seed.id, hop1.id, strength=0.7)
    assoc2 = _make_association(hop1.id, hop2.id, strength=0.6)
    db_session.add_all([assoc1, assoc2])
    await db_session.commit()

    svc = MemoryRecallService(db_session)

    # depth=1 should only reach hop1
    results_d1 = await svc.recall_graph_connected(seed.id, depth=1, min_strength=0.3)
    ids_d1 = {m.id for m in results_d1}
    assert hop1.id in ids_d1
    assert hop2.id not in ids_d1

    # depth=2 should reach both
    results_d2 = await svc.recall_graph_connected(seed.id, depth=2, min_strength=0.3)
    ids_d2 = {m.id for m in results_d2}
    assert hop1.id in ids_d2
    assert hop2.id in ids_d2


@pytest.mark.asyncio
async def test_strength_filter(db_session: AsyncSession):
    """Edges below min_strength are excluded from traversal."""
    user_id = uuid4()
    family_id = uuid4()

    seed = _make_memory(user_id, family_id, summary="seed")
    strong = _make_memory(user_id, family_id, summary="strong link")
    weak = _make_memory(user_id, family_id, summary="weak link")
    db_session.add_all([seed, strong, weak])
    await db_session.flush()

    assoc_strong = _make_association(seed.id, strong.id, strength=0.8)
    assoc_weak = _make_association(seed.id, weak.id, strength=0.1)
    db_session.add_all([assoc_strong, assoc_weak])
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_graph_connected(seed.id, depth=1, min_strength=0.3)
    result_ids = {m.id for m in results}

    assert strong.id in result_ids, "Strong edge should be included"
    assert weak.id not in result_ids, "Weak edge should be filtered out"


@pytest.mark.asyncio
async def test_superseded_filtered(db_session: AsyncSession):
    """SUPERSEDED memories are excluded from graph results."""
    user_id = uuid4()
    family_id = uuid4()

    seed = _make_memory(user_id, family_id, summary="seed")
    active_mem = _make_memory(user_id, family_id, summary="active")
    superseded_mem = _make_memory(
        user_id, family_id,
        summary="superseded",
        status=MemoryStatus.SUPERSEDED.value,
    )
    db_session.add_all([seed, active_mem, superseded_mem])
    await db_session.flush()

    assoc1 = _make_association(seed.id, active_mem.id, strength=0.7)
    assoc2 = _make_association(seed.id, superseded_mem.id, strength=0.7)
    db_session.add_all([assoc1, assoc2])
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_graph_connected(seed.id, depth=1, min_strength=0.3)
    result_ids = {m.id for m in results}

    assert active_mem.id in result_ids
    assert superseded_mem.id not in result_ids, "SUPERSEDED memory should be excluded"


@pytest.mark.asyncio
async def test_zero_depth_returns_empty(db_session: AsyncSession):
    """depth=0 should return an empty list."""
    user_id = uuid4()
    family_id = uuid4()

    seed = _make_memory(user_id, family_id, summary="seed")
    neighbour = _make_memory(user_id, family_id, summary="neighbour")
    db_session.add_all([seed, neighbour])
    await db_session.flush()

    assoc = _make_association(seed.id, neighbour.id, strength=0.8)
    db_session.add(assoc)
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_graph_connected(seed.id, depth=0, min_strength=0.3)
    assert results == []


@pytest.mark.asyncio
async def test_no_associations_returns_empty(db_session: AsyncSession):
    """A memory with no associations should return an empty list."""
    user_id = uuid4()
    family_id = uuid4()

    seed = _make_memory(user_id, family_id, summary="lonely seed")
    db_session.add(seed)
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_graph_connected(seed.id, depth=2, min_strength=0.3)
    assert results == []


# ---------------------------------------------------------------------------
# recall_related_to_entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_match_basic(db_session: AsyncSession):
    """Memories containing the entity in JSONB are returned."""
    user_id = uuid4()
    family_id = uuid4()

    mem_match = _make_memory(
        user_id, family_id,
        summary="likes coffee",
        entities={"person": "Alice", "preference": "coffee"},
    )
    mem_no_match = _make_memory(
        user_id, family_id,
        summary="unrelated",
        entities={"person": "Bob"},
    )
    db_session.add_all([mem_match, mem_no_match])
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_related_to_entity("Alice", family_id, max_results=10)
    result_ids = {m.id for m in results}

    assert mem_match.id in result_ids, "Memory with matching entity should be found"
    assert mem_no_match.id not in result_ids, "Memory without matching entity should not appear"


@pytest.mark.asyncio
async def test_entity_one_hop_expansion(db_session: AsyncSession):
    """1-hop expansion through associations includes connected memories."""
    user_id = uuid4()
    family_id = uuid4()

    seed_mem = _make_memory(
        user_id, family_id,
        summary="Alice birthday",
        entities={"person": "Alice"},
        importance=8,
    )
    connected_mem = _make_memory(
        user_id, family_id,
        summary="gift idea",
        entities={"topic": "gift"},
        importance=6,
    )
    db_session.add_all([seed_mem, connected_mem])
    await db_session.flush()

    assoc = _make_association(seed_mem.id, connected_mem.id, strength=0.7)
    db_session.add(assoc)
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_related_to_entity("Alice", family_id, max_results=10)
    result_ids = {m.id for m in results}

    assert seed_mem.id in result_ids, "Seed entity match should be in results"
    assert connected_mem.id in result_ids, "1-hop connected memory should be expanded"


@pytest.mark.asyncio
async def test_entity_superseded_excluded(db_session: AsyncSession):
    """SUPERSEDED memories are excluded from entity recall."""
    user_id = uuid4()
    family_id = uuid4()

    active_mem = _make_memory(
        user_id, family_id,
        summary="Alice active",
        entities={"person": "Alice"},
    )
    superseded_mem = _make_memory(
        user_id, family_id,
        summary="Alice old",
        entities={"person": "Alice"},
        status=MemoryStatus.SUPERSEDED.value,
    )
    db_session.add_all([active_mem, superseded_mem])
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_related_to_entity("Alice", family_id, max_results=10)
    result_ids = {m.id for m in results}

    assert active_mem.id in result_ids
    assert superseded_mem.id not in result_ids, "SUPERSEDED should be excluded"


@pytest.mark.asyncio
async def test_entity_ranking_by_importance(db_session: AsyncSession):
    """Results are ranked by importance * recency_decay, highest first."""
    user_id = uuid4()
    family_id = uuid4()

    high_imp = _make_memory(
        user_id, family_id,
        summary="Alice important",
        entities={"person": "Alice"},
        importance=9,
    )
    low_imp = _make_memory(
        user_id, family_id,
        summary="Alice minor",
        entities={"person": "Alice"},
        importance=2,
    )
    db_session.add_all([high_imp, low_imp])
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_related_to_entity("Alice", family_id, max_results=10)

    assert len(results) >= 2
    assert results[0].id == high_imp.id, "Higher importance memory should rank first"


@pytest.mark.asyncio
async def test_entity_max_results_limit(db_session: AsyncSession):
    """Results are limited by max_results parameter."""
    user_id = uuid4()
    family_id = uuid4()

    memories = []
    for i in range(5):
        mem = _make_memory(
            user_id, family_id,
            summary=f"Alice memory {i}",
            entities={"person": "Alice"},
            importance=5,
        )
        memories.append(mem)

    db_session.add_all(memories)
    await db_session.commit()

    svc = MemoryRecallService(db_session)
    results = await svc.recall_related_to_entity("Alice", family_id, max_results=3)

    assert len(results) <= 3, "Should respect max_results limit"
