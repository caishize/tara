"""
Trip grouping logic for the curation system.

Implements a 3-phase interval merging algorithm that groups events into trips
using destination + date continuity.

Phase 1: Group by trip_id (preserves road trips as one unit)
Phase 2: Split within each group where date gap > max_gap_days
Phase 3: Merge across groups if same destination + adjacent dates
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from ....core.utils.timezone import to_local_date


@dataclass
class SubGroup:
    """A group of events that belong to the same logical trip."""

    events: list
    trip_ids: Set[Optional[UUID]] = field(default_factory=set)


def normalize_destination(city: Optional[str]) -> str:
    """Basic cleanup only. Semantic normalization is LLM's job."""
    if not city:
        return ""
    return city.strip().lower()


def local_start_date(event: Any, user_tz: Any) -> date:
    """Get the local start date of an event."""
    if not event.normalized_start:
        raise ValueError("Event has no normalized_start")
    return to_local_date(event.normalized_start, user_tz)


def local_end_date(event: Any, user_tz: Any) -> date:
    """Get the local end date of an event, falling back to start date."""
    dt = event.normalized_end or event.normalized_start
    if not dt:
        raise ValueError("Event has no start or end time")
    return to_local_date(dt, user_tz)


def _get_event_city(event: Any) -> Optional[str]:
    """Get the city field from an event, with fallback to location."""
    city = getattr(event, "city", None)
    if city:
        return city

    location = getattr(event, "location", None)
    if not location:
        return None

    if "\u2192" in location or "->" in location:
        return None

    return location


def split_by_date_gaps(
    events: list,
    user_tz: Any,
    max_gap_days: int = 1,
) -> List[list]:
    """Split a list of events into sub-lists where date gaps exceed max_gap_days."""
    if not events:
        return []

    sorted_events = sorted(
        events,
        key=lambda e: to_local_date(e.normalized_start or e.normalized_end, user_tz),
    )

    groups: List[list] = [[sorted_events[0]]]
    prev_end = local_end_date(sorted_events[0], user_tz)

    for event in sorted_events[1:]:
        curr_start = local_start_date(event, user_tz)
        gap = (curr_start - prev_end).days

        if gap > max_gap_days:
            groups.append([event])
        else:
            groups[-1].append(event)

        curr_end = local_end_date(event, user_tz)
        if curr_end > prev_end:
            prev_end = curr_end

    return groups


def get_subgroup_destination(events: list) -> Optional[str]:
    """Determine the destination for a sub-group of events."""
    cities: Set[str] = set()
    for event in events:
        city = _get_event_city(event)
        normalized = normalize_destination(city)
        if normalized:
            cities.add(normalized)

    if len(cities) == 1:
        return cities.pop()
    return None


def _subgroup_date_range(sg: SubGroup, user_tz: Any) -> Tuple[date, date]:
    """Get the (min_start, max_end) date range of a sub-group."""
    starts = [local_start_date(e, user_tz) for e in sg.events if e.normalized_start]
    ends = [local_end_date(e, user_tz) for e in sg.events if e.normalized_start]
    return min(starts), max(ends)


def merge_adjacent_subgroups(
    sub_groups: List[SubGroup],
    user_tz: Any,
    max_gap_days: int = 1,
) -> List[SubGroup]:
    """Merge sub-groups that share the same destination and are date-adjacent."""
    if not sub_groups:
        return []

    annotated: List[Tuple[SubGroup, Optional[str], date, date]] = []
    for sg in sub_groups:
        dest = get_subgroup_destination(sg.events)
        if sg.events and any(e.normalized_start for e in sg.events):
            start, end = _subgroup_date_range(sg, user_tz)
            annotated.append((sg, dest, start, end))
        else:
            annotated.append((sg, dest, date.min, date.min))

    annotated.sort(key=lambda x: x[2])

    merged: List[Tuple[SubGroup, Optional[str], date, date]] = [annotated[0]]

    for sg, dest, start, end in annotated[1:]:
        prev_sg, prev_dest, prev_start, prev_end = merged[-1]

        can_merge = (
            dest is not None
            and prev_dest is not None
            and dest == prev_dest
            and (start - prev_end).days <= max_gap_days
        )

        if can_merge:
            combined_events = prev_sg.events + sg.events
            combined_trip_ids = prev_sg.trip_ids | sg.trip_ids
            new_end = max(prev_end, end)
            merged[-1] = (
                SubGroup(events=combined_events, trip_ids=combined_trip_ids),
                prev_dest,
                prev_start,
                new_end,
            )
        else:
            merged.append((sg, dest, start, end))

    return [item[0] for item in merged]


def group_events_into_trips(
    all_events: list,
    user_tz: Any,
    max_gap_days: int = 1,
) -> List[SubGroup]:
    """Full 3-phase pipeline for grouping events into logical trips."""
    if not all_events:
        return []

    INTRA_TRIP_MAX_GAP_DAYS = 7

    # Phase 1: Group by trip_id
    trip_groups: Dict[str, list] = {}
    for event in all_events:
        if event.trip_id:
            key = str(event.trip_id)
        else:
            key = f"_solo_{event.id}"
        trip_groups.setdefault(key, []).append(event)

    # Phase 2: Split within each group by date gaps
    sub_groups: List[SubGroup] = []
    for group_key, events in trip_groups.items():
        trip_ids = {e.trip_id for e in events}
        is_trip_group = not group_key.startswith("_solo_")

        valid_events = [e for e in events if e.normalized_start]
        invalid_events = [e for e in events if not e.normalized_start]

        if not valid_events:
            sub_groups.append(SubGroup(events=events, trip_ids=trip_ids))
            continue

        phase2_gap = INTRA_TRIP_MAX_GAP_DAYS if is_trip_group else max_gap_days
        splits = split_by_date_gaps(valid_events, user_tz, phase2_gap)
        for split_events in splits:
            sub_groups.append(SubGroup(events=split_events, trip_ids=trip_ids))

        for inv_event in invalid_events:
            sub_groups.append(SubGroup(events=[inv_event], trip_ids=trip_ids))

    # Phase 3: Merge across groups if same destination + adjacent dates
    merged = merge_adjacent_subgroups(sub_groups, user_tz, max_gap_days)

    return merged
