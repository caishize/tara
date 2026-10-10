"""Trip query scene policy.

Centralizes scene-aware query behavior used by trip retrieval tools.
"""

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Tuple, cast

TripQueryScene = Literal[
    "default",
    "current_plan",
    "past_executed",
    "past_planned",
    "referenced_plan",
]

DateScope = Literal["all", "past_only", "current_or_future"]

_VALID_SCENES = {
    "default",
    "current_plan",
    "past_executed",
    "past_planned",
    "referenced_plan",
}

_SCENE_INCLUDE_HISTORY_DEFAULT = {
    "past_planned",
    "referenced_plan",
}


@dataclass(frozen=True)
class TripQueryPolicy:
    """Resolved scene policy for trip lookup."""

    scene: TripQueryScene
    include_history: bool
    date_scope: DateScope
    status_include: Tuple[str, ...]
    status_exclude: Tuple[str, ...]


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def resolve_trip_query_policy(args: Mapping[str, Any]) -> TripQueryPolicy:
    """Resolve scene/include_history policy from tool args."""
    raw_scene = str(args.get("query_scene") or "").strip()
    scene = cast(
        TripQueryScene,
        raw_scene if raw_scene in _VALID_SCENES else "default",
    )

    include_history_provided = "include_history" in args
    include_history = _to_bool(args.get("include_history"), default=False)
    if not include_history_provided and scene in _SCENE_INCLUDE_HISTORY_DEFAULT:
        include_history = True

    if scene == "current_plan":
        return TripQueryPolicy(
            scene=scene,
            include_history=include_history,
            date_scope="current_or_future",
            status_include=(),
            status_exclude=("cancelled", "completed"),
        )

    if scene == "past_executed":
        return TripQueryPolicy(
            scene=scene,
            include_history=include_history,
            date_scope="past_only",
            status_include=("completed", "confirmed", "in_progress"),
            status_exclude=(),
        )

    if scene in {"past_planned", "referenced_plan"}:
        return TripQueryPolicy(
            scene=scene,
            include_history=include_history,
            date_scope="past_only",
            status_include=("planning", "confirmed", "in_progress"),
            status_exclude=(),
        )

    return TripQueryPolicy(
        scene="default",
        include_history=include_history,
        date_scope="all",
        status_include=(),
        status_exclude=(),
    )
