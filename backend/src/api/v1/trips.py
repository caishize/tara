"""Trip API routes - /api/v1/trips/*

Thin routing layer for trip plan management, itineraries, expenses,
itinerary versions, and destination search.

Re-exports the existing trip module routers.

Endpoints:
    GET/POST     /trips/plans                                   - Plan list/create
    GET/PUT/DEL  /trips/plans/{id}                              - Single plan ops
    GET/POST     /trips/plans/{id}/itinerary                    - Itinerary management
    POST         /trips/plans/{id}/itinerary/generate           - Basic itinerary generation
    POST         /trips/plans/{id}/itinerary/generate-smart     - Smart itinerary generation
    PUT          /trips/plans/{id}/itinerary/day/{d}/activity   - Update day activity
    POST         /trips/plans/{id}/itinerary/day/{d}/activity   - Add day activity
    DELETE       /trips/plans/{id}/itinerary/day/{d}/activity/i - Delete day activity
    POST         /trips/plans/{id}/itinerary/swap-days          - Swap two days
    GET/POST/PUT/DEL /trips/plans/{id}/versions/*               - Itinerary versions
    GET/POST     /trips/plans/{id}/expenses                     - Expense management
    GET          /trips/plans/{id}/expenses/budget-status       - Budget status
    POST         /trips/recommend                               - Destination recommendations
    GET          /trips/destinations/search                     - Destination search
"""

from fastapi import APIRouter

# Auth: core.auth (get_current_user/get_current_family) is used in sub-routers
from ...modules.trip.api import (
    trip_plan_router,
    itinerary_router,
    itinerary_version_router,
    expense_router,
    destination_router,
)

# Aggregate router that includes all trip sub-routers
router = APIRouter(tags=["trips"])
router.include_router(trip_plan_router)
router.include_router(itinerary_router)
router.include_router(itinerary_version_router)
router.include_router(expense_router)
router.include_router(destination_router)
