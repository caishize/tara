"""Information triage: classify InsightCandidates into delivery tiers.

Each candidate is assigned an InformationTier (L0_AUTO / L1_PASSIVE / L2_FORMAL)
based on deterministic rules over urgency, importance, and insight type.

Immutable: returns new InsightCandidate instances, never mutates.
"""

from __future__ import annotations

import dataclasses
from typing import List

from .models import InformationTier, InsightCandidate, InsightType


class InformationTriage:
    """Classifies insight candidates into delivery tiers.

    L0_AUTO   — Secretary handles autonomously, no user interruption.
    L1_PASSIVE — Mentioned casually during next user interaction.
    L2_FORMAL  — Proactively pushed, requires user attention/decision.
    """

    def classify(self, candidate: InsightCandidate) -> InsightCandidate:
        """Return a new candidate with information_tier set (immutable)."""
        tier = self._compute_tier(candidate)
        return dataclasses.replace(candidate, information_tier=tier)

    def classify_batch(self, candidates: List[InsightCandidate]) -> List[InsightCandidate]:
        """Classify a list of candidates. Returns new list (immutable)."""
        return [self.classify(c) for c in candidates]

    def _compute_tier(self, c: InsightCandidate) -> str:
        """Determine the appropriate delivery tier for a candidate."""
        source = c.source_context or {}

        # ── L0: Auto-resolvable (no user action needed) ──────────────
        if source.get("auto_resolvable"):
            return InformationTier.L0_AUTO.value

        # ── L0: Positive affirmations with low urgency ───────────────
        if (
            c.insight_type == InsightType.POSITIVE_AFFIRMATION.value
            and c.urgency < 30
        ):
            return InformationTier.L0_AUTO.value

        # ── L0: Confirmed bookings (informational only) ──────────────
        if source.get("confirmed_booking"):
            return InformationTier.L0_AUTO.value

        # ── L1: Low urgency + low importance (not worth interrupting) ─
        if c.urgency < 40 and c.importance < 50:
            return InformationTier.L1_PASSIVE.value

        # ── L1: Weather care that isn't severe ───────────────────────
        if (
            c.insight_type == InsightType.WEATHER_CARE.value
            and c.importance < 60
        ):
            return InformationTier.L1_PASSIVE.value

        # ── L1: Trend alerts below medium importance ─────────────────
        if (
            c.insight_type == InsightType.TREND_ALERT.value
            and c.importance < 55
            and c.urgency < 50
        ):
            return InformationTier.L1_PASSIVE.value

        # ── L2: Everything else (proactive push) ─────────────────────
        return InformationTier.L2_FORMAL.value
