"""Relationship algorithms - decay, intimacy scoring, health calculation."""

from .relationship_decay import (
    RelationshipCategory,
    RelationshipDecayCalculator,
    FAMILY_RELATION_TYPES,
    NETWORK_RELATION_TYPES,
)

__all__ = [
    "RelationshipCategory",
    "RelationshipDecayCalculator",
    "FAMILY_RELATION_TYPES",
    "NETWORK_RELATION_TYPES",
]
