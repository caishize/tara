"""Shared ContactTier resolution utilities.

Centralises the importance-to-tier mapping so that every signal collector
and the rule engine use consistent thresholds.
"""

from __future__ import annotations

from ...relationship.models import ContactTier


def resolve_tier(importance: int) -> ContactTier:
    """Map a PersonProfile.importance score (1-10) to a ContactTier.

    Thresholds (aligned with PersonProfile.importance column, scale 1-10):
        >= 8  ->  CORE       (至亲)
        >= 5  ->  IMPORTANT  (挚友)
        <  5  ->  GENERAL    (一般)
    """
    if importance >= 8:
        return ContactTier.CORE
    if importance >= 5:
        return ContactTier.IMPORTANT
    return ContactTier.GENERAL
