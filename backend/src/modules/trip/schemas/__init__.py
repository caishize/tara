"""
Trip planning schemas.
"""
from .trip_plan import (
    TripPlanBase,
    TripPlanCreate,
    TripPlanUpdate,
    TripPlanResponse,
    TripPlanListResponse,
)
from .itinerary import (
    ItineraryItemSchema,
    TripItineraryBase,
    TripItineraryCreate,
    TripItineraryUpdate,
    TripItineraryResponse,
    TripItineraryListResponse,
)
from .expense import (
    TripExpenseBase,
    TripExpenseCreate,
    TripExpenseUpdate,
    TripExpenseResponse,
    TripExpenseListResponse,
    BudgetStatusResponse,
)
from .memory import (
    TripMemoryBase,
    TripMemoryCreate,
    TripMemoryUpdate,
    TripMemoryResponse,
    TripMemoryListResponse,
    MemoryAlbumResponse,
)

# Backward-compatible aliases
TravelPlanBase = TripPlanBase
TravelPlanCreate = TripPlanCreate
TravelPlanUpdate = TripPlanUpdate
TravelPlanResponse = TripPlanResponse
TravelPlanListResponse = TripPlanListResponse
TravelItineraryBase = TripItineraryBase
TravelItineraryCreate = TripItineraryCreate
TravelItineraryUpdate = TripItineraryUpdate
TravelItineraryResponse = TripItineraryResponse
TravelItineraryListResponse = TripItineraryListResponse
TravelExpenseBase = TripExpenseBase
TravelExpenseCreate = TripExpenseCreate
TravelExpenseUpdate = TripExpenseUpdate
TravelExpenseResponse = TripExpenseResponse
TravelExpenseListResponse = TripExpenseListResponse
TravelMemoryBase = TripMemoryBase
TravelMemoryCreate = TripMemoryCreate
TravelMemoryUpdate = TripMemoryUpdate
TravelMemoryResponse = TripMemoryResponse
TravelMemoryListResponse = TripMemoryListResponse

__all__ = [
    # Trip Plan
    "TripPlanBase",
    "TripPlanCreate",
    "TripPlanUpdate",
    "TripPlanResponse",
    "TripPlanListResponse",
    # Itinerary
    "ItineraryItemSchema",
    "TripItineraryBase",
    "TripItineraryCreate",
    "TripItineraryUpdate",
    "TripItineraryResponse",
    "TripItineraryListResponse",
    # Expense
    "TripExpenseBase",
    "TripExpenseCreate",
    "TripExpenseUpdate",
    "TripExpenseResponse",
    "TripExpenseListResponse",
    "BudgetStatusResponse",
    # Memory
    "TripMemoryBase",
    "TripMemoryCreate",
    "TripMemoryUpdate",
    "TripMemoryResponse",
    "TripMemoryListResponse",
    "MemoryAlbumResponse",
]
