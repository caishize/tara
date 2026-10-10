"""
Heuristic deduplication utilities for event curation.

Pure functions using stdlib only (difflib.SequenceMatcher).
Used as fallback when LLM dedup fails.
"""
import re
from collections import defaultdict
from difflib import SequenceMatcher
from datetime import datetime
from typing import Dict, List, Optional


# Common filler words to strip for title comparison
_FILLER_WORDS = re.compile(r"(的|行程|之旅|旅行|出差|计划|安排|游|旅游)")

# Whitespace normalization
_WHITESPACE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Strip whitespace and common filler words for comparison."""
    text = _WHITESPACE.sub("", title.strip())
    text = _FILLER_WORDS.sub("", text)
    return text


def title_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio (0-1) between two titles."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def date_overlaps(
    start_a: Optional[datetime],
    end_a: Optional[datetime],
    start_b: Optional[datetime],
    end_b: Optional[datetime],
) -> bool:
    """Check if two date ranges overlap."""
    if start_a is None or start_b is None:
        return False

    eff_end_a = end_a or start_a
    eff_end_b = end_b or start_b

    return start_a <= eff_end_b and start_b <= eff_end_a


def normalize_location(loc: Optional[str]) -> str:
    """Normalize a location string for comparison."""
    if not loc:
        return ""
    return _WHITESPACE.sub("", loc.strip().lower())


def location_matches(loc_a: Optional[str], loc_b: Optional[str]) -> bool:
    """Check if two locations match after normalization."""
    na = normalize_location(loc_a)
    nb = normalize_location(loc_b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _both_have_locations(loc_a: Optional[str], loc_b: Optional[str]) -> bool:
    """Return True when both locations are non-empty after normalization."""
    return bool(normalize_location(loc_a)) and bool(normalize_location(loc_b))


def should_merge(
    event_a: dict,
    event_b: dict,
    threshold: float = 0.6,
) -> bool:
    """Determine if two raw events should be merged."""
    norm_a = normalize_title(event_a.get("title", ""))
    norm_b = normalize_title(event_b.get("title", ""))
    sim = title_similarity(norm_a, norm_b)

    overlap = date_overlaps(
        event_a.get("start_time"),
        event_a.get("end_time"),
        event_b.get("start_time"),
        event_b.get("end_time"),
    )

    loc_a = event_a.get("location")
    loc_b = event_b.get("location")
    loc_match = location_matches(loc_a, loc_b)

    # Hard veto: conflicting locations with date overlap
    if overlap and _both_have_locations(loc_a, loc_b) and not loc_match:
        return False

    # Guard: require higher title similarity when dates overlap
    if overlap and sim < 0.7:
        return False

    score = sim * 0.5 + (1.0 if overlap else 0.0) * 0.3 + (1.0 if loc_match else 0.0) * 0.2
    return score >= threshold


def cluster_events(events: List[dict]) -> List[List[dict]]:
    """Group events that should be merged using Union-Find."""
    n = len(events)
    if n == 0:
        return []

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if should_merge(events[i], events[j]):
                union(i, j)

    clusters: Dict[int, List[dict]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(events[i])

    return list(clusters.values())
