"""InsightSignalCollector — Collects signals from all domain sources.

Orchestrates parallel signal collection by delegating to sub-modules
in the ``signals/`` package.  Each signal category lives in its own file
for maintainability; this module owns only the AllSignals container and
the ``collect_all`` orchestration logic.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from .signals import (
    collect_association_signals,
    collect_commitment_signals,
    collect_event_signals,
    collect_favor_signals,
    collect_graph_signals,
    collect_holiday_signals,
    collect_memory_signals,
    collect_preference_signals,
    collect_relationship_signals,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal container
# ---------------------------------------------------------------------------

_SIGNAL_CATEGORIES = (
    "protected",
    "events",
    "holidays",
    "relationships",
    "memories",
    "associations",
    "graph",
    "preferences",
)


@dataclass
class AllSignals:
    """Container for all signal types collected for insight generation."""

    protected: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    holidays: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    memories: List[Dict[str, Any]] = field(default_factory=list)
    associations: List[Dict[str, Any]] = field(default_factory=list)
    graph: List[Dict[str, Any]] = field(default_factory=list)
    preferences: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, category: str, item: Dict[str, Any]) -> None:
        """Append an item to the given signal category."""
        target = getattr(self, category, None)
        if target is None:
            logger.warning("Unknown signal category: %s", category)
            return
        target.append(item)

    def get_all_entity_ids(self) -> Set[UUID]:
        """Collect all entity UUIDs referenced across every signal."""
        ids: Set[UUID] = set()
        _ENTITY_KEYS = (
            "id", "event_id", "person_id", "member_id",
            "favor_record_id", "commitment_id", "important_date_id",
            "person_a_id", "person_b_id",
        )
        for category in _SIGNAL_CATEGORIES:
            for item in getattr(self, category, []):
                for key in _ENTITY_KEYS:
                    val = item.get(key)
                    if val is not None:
                        try:
                            ids.add(
                                UUID(str(val))
                                if not isinstance(val, UUID)
                                else val
                            )
                        except (ValueError, AttributeError):
                            pass
        return ids

    def total_count(self) -> int:
        return sum(len(getattr(self, cat, [])) for cat in _SIGNAL_CATEGORIES)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class InsightSignalCollector:
    """Collects signals from all domain sources for insight generation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def collect_all(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
    ) -> AllSignals:
        """Collect signals from all sources in parallel."""
        signals = AllSignals()

        # Each tuple: (category_name, coroutine)
        collectors = [
            ("protected", self._collect_protected_signals(user_id, family_id)),
            ("events", collect_event_signals(self.db, family_id, target_date)),
            (
                "holidays",
                collect_holiday_signals(self.db, family_id, target_date),
            ),
            (
                "relationships",
                collect_relationship_signals(self.db, family_id, user_id),
            ),
            ("memories", collect_memory_signals(self.db, user_id)),
            (
                "associations",
                collect_association_signals(self.db, family_id, target_date),
            ),
            ("graph", collect_graph_signals(self.db, family_id)),
            ("preferences", collect_preference_signals(self.db, user_id)),
        ]

        results = await asyncio.gather(
            *(coro for _, coro in collectors),
            return_exceptions=True,
        )

        for (name, _), items in zip(collectors, results):
            if isinstance(items, Exception):
                logger.error("Signal collection failed for %s: %s", name, items)
            elif items:
                for item in items:
                    signals.add(name, item)

        return signals

    # ------------------------------------------------------------------
    # Protected signals: favors + urgent commitments (combined category)
    # ------------------------------------------------------------------

    async def _collect_protected_signals(
        self, user_id: UUID, family_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Collect protected signals: pending favors and urgent commitments.

        Favor signals are enriched with L2/L3 relationship capital data
        and reciprocation opportunities (best-effort).
        """
        favor_items, commitment_items = await asyncio.gather(
            collect_favor_signals(self.db, family_id),
            collect_commitment_signals(self.db, user_id, family_id),
        )
        protected = [*favor_items, *commitment_items]
        return await self._enrich_favor_signals_with_depth(protected, user_id)

    async def _enrich_favor_signals_with_depth(
        self,
        signals: List[Dict[str, Any]],
        user_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Enrich favor signals with L2/L3 relationship capital data.

        Also appends reciprocation opportunity signals. Best-effort:
        failures are logged and original signals returned unchanged.
        """
        try:
            from .favor_depth_model import (
                compute_relationship_capital,
                find_reciprocation_opportunities,
            )
        except ImportError:
            return signals

        enriched: List[Dict[str, Any]] = []
        for sig in signals:
            if sig.get("signal_type") != "favor" or not sig.get("contact_id"):
                enriched.append(sig)
                continue

            try:
                contact_uuid = UUID(sig["contact_id"])
                capital = await compute_relationship_capital(
                    self.db, user_id, contact_uuid,
                )
                enriched.append({
                    **sig,
                    "l1_balance": capital.l1_balance,
                    "l2_score": capital.l2_score,
                    "l3_overall": capital.l3_overall,
                    "relationship_trend": capital.trend,
                })
            except Exception as exc:
                logger.debug(
                    "L2/L3 enrichment failed for contact %s: %s",
                    sig.get("contact_id"), exc,
                )
                enriched.append(sig)

        # Append reciprocation opportunities as additional signals
        try:
            opportunities = await find_reciprocation_opportunities(
                self.db, user_id,
            )
            for opp in opportunities:
                enriched.append({
                    **opp,
                    "signal_type": "reciprocation_opportunity",
                })
        except Exception as exc:
            logger.debug("Reciprocation opportunity scan failed: %s", exc)

        return enriched
