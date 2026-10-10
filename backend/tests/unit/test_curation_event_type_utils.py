from src.modules.curation.services.event_type_utils import (
    map_important_date_type,
    normalize_event_type,
)


def test_map_important_date_type_keeps_solar_term_types():
    assert map_important_date_type("holiday_solar_term") == "holiday_solar_term"
    assert map_important_date_type("solar_term") == "solar_term"


def test_map_important_date_type_maps_lunar_holiday_to_holiday():
    assert map_important_date_type("holiday_lunar") == "holiday"


def test_normalize_event_type_uses_default_for_unknown():
    assert normalize_event_type("unknown_type", default="appointment") == "appointment"
