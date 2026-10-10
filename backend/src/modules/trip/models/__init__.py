"""
Trip planning models.
"""
from .trip_plan import TripPlan
from .trip_itinerary import TripItinerary
from .trip_expense import TripExpense
from .trip_memory import TripMemory
from .itinerary_version import ItineraryVersion

# Backward-compatible aliases
TravelPlan = TripPlan
TravelItinerary = TripItinerary
TravelExpense = TripExpense
TravelMemory = TripMemory

__all__ = [
    "TripPlan",
    "TripItinerary",
    "TripExpense",
    "TripMemory",
    "ItineraryVersion",
    # Backward-compatible aliases (will be removed after full migration)
    "TravelPlan",
    "TravelItinerary",
    "TravelExpense",
    "TravelMemory",
]
