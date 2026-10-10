"""Relationship module - manage social obligations and care.

Records favor exchanges, visualizes relationship health,
and generates smart care suggestions.
"""

from .interface import (
    IFavorService,
    ICareService,
    FavorRecord,
    FavorBalance,
    CareSuggestion,
    RelationshipHealth,
)
from .favor_service import FavorService
from .care_service import CareService

__all__ = [
    "IFavorService",
    "ICareService",
    "FavorRecord",
    "FavorBalance",
    "CareSuggestion",
    "RelationshipHealth",
    "FavorService",
    "CareService",
]
