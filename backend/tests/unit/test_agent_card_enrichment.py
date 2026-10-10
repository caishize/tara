from src.ai_engine.workers.agent_helpers import extract_card_enrichment
from src.modules.conversation.card_normalizer import (
    normalize,
    normalize_query_trips_data,
)


def test_extract_card_enrichment_prefers_latest_when_priority_is_equal():
    collected_tool_calls = [
        {
            "status": "success",
            "tool_name": "query_trips",
            "full_result": {
                "trips": [
                    {
                        "id": "old-trip",
                        "title": "广州圣心大教堂",
                        "location": "广州圣心大教堂",
                        "start_date": "2026-03-01",
                        "end_date": "2026-03-04",
                        "status": "planning",
                    }
                ]
            },
        },
        {
            "status": "success",
            "tool_name": "update_trip",
            "full_result": {
                "trip_id": "new-trip",
                "trip_name": "广州美食文化之旅",
                "destination": "广州",
                "start_date": "2026-03-01",
                "end_date": "2026-03-04",
                "status": "planning",
            },
        },
    ]

    enrichment = extract_card_enrichment(collected_tool_calls)

    assert enrichment is not None
    assert enrichment["intent"] == "trip_itinerary"
    assert enrichment["data"]["trip_name"] == "广州美食文化之旅"


def test_normalize_query_trips_data_keeps_trip_name_and_destination_separately():
    intent, normalized = normalize_query_trips_data({
        "trips": [
            {
                "id": "trip-1",
                "title": "广州美食文化之旅",
                "location": "广州圣心大教堂",
                "start_date": "2026-03-01",
                "end_date": "2026-03-04",
                "status": "planning",
            }
        ]
    })

    assert intent == "trip_itinerary"
    assert normalized["trip_name"] == "广州美食文化之旅"
    assert normalized["title"] == "广州美食文化之旅"
    assert normalized["destination"] == "广州圣心大教堂"


def test_normalized_trip_card_title_prefers_trip_name_over_destination():
    card = normalize(
        "update_trip",
        {
            "trip_name": "广州美食文化之旅",
            "destination": "广州圣心大教堂",
        },
    )

    assert card is not None
    assert card.title == "广州美食文化之旅"
