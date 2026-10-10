"""Collect social graph signals: weak edges and key connectors.

Extracted from InsightSignalCollector._collect_graph_signals.
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_WEAK_THRESHOLD = 0.3
_KEY_CONNECTOR_MIN_EDGES = 3


async def collect_graph_signals(
    db: AsyncSession,
    family_id: UUID,
) -> List[Dict[str, Any]]:
    """Return weak relationships and key connector persons."""
    from ...member.models.relationship import RelationshipEdge

    stmt = (
        select(RelationshipEdge)
        .where(RelationshipEdge.family_id == family_id)
        .limit(200)
    )
    result = await db.execute(stmt)
    edges = list(result.scalars().all())

    if not edges:
        return []

    signals: List[Dict[str, Any]] = []

    # --- Weak / cooling relationships (strength < threshold) ---
    for edge in edges:
        strength = edge.strength if edge.strength is not None else 0.5
        if strength < _WEAK_THRESHOLD:
            signals.append({
                "signal_type": "weak_relationship",
                "person_a_id": str(edge.person_a_id),
                "person_b_id": str(edge.person_b_id),
                "relationship_type": edge.relationship_type,
                "strength": strength,
                "context": edge.context,
            })

    # --- Key connector persons (appearing in 3+ edges) ---
    person_edge_counts: Dict[str, int] = {}
    for edge in edges:
        a_id = str(edge.person_a_id)
        b_id = str(edge.person_b_id)
        person_edge_counts = {
            **person_edge_counts,
            a_id: person_edge_counts.get(a_id, 0) + 1,
            b_id: person_edge_counts.get(b_id, 0) + 1,
        }

    for person_id, count in person_edge_counts.items():
        if count >= _KEY_CONNECTOR_MIN_EDGES:
            signals.append({
                "signal_type": "key_connector",
                "person_a_id": person_id,
                "person_b_id": None,
                "relationship_type": None,
                "strength": None,
                "context": None,
                "edge_count": count,
            })

    return signals
