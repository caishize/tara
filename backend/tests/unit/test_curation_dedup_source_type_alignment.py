from datetime import datetime, timezone

from src.modules.curation.services.data_models import RawEvent
from src.modules.curation.services.dedup_service import _align_event_type_with_sources


def _raw_event(event_id: str, source_type: str, event_type: str) -> RawEvent:
    return RawEvent(
        id=event_id,
        source_type=source_type,
        title=f"{event_id}-title",
        start_time=datetime.now(timezone.utc),
        event_type=event_type,
    )


def test_align_event_type_preserves_solar_term_for_important_date_sources() -> None:
    merged_raw = [_raw_event("d1", "important_date", "solar_term")]
    aligned = _align_event_type_with_sources(
        "holiday",
        source_types=["important_date"],
        merged_raw_events=merged_raw,
    )
    assert aligned == "solar_term"


def test_align_event_type_preserves_birthday_over_generic_llm_output() -> None:
    merged_raw = [_raw_event("d2", "important_date", "birthday")]
    aligned = _align_event_type_with_sources(
        "reminder",
        source_types=["important_date"],
        merged_raw_events=merged_raw,
    )
    assert aligned == "birthday"


def test_align_event_type_does_not_override_non_important_date_sources() -> None:
    merged_raw = [_raw_event("e1", "trip_plan", "travel")]
    aligned = _align_event_type_with_sources(
        "meeting",
        source_types=["trip_plan"],
        merged_raw_events=merged_raw,
    )
    assert aligned == "meeting"
