"""
Intervention module for full-duplex conversation support.

Provides intervention classification, signal handling, and session state
management for real-time user message interception during active generation.
"""

from .types import (
    GenerationState,
    InterventionType,
    InterventionSignal,
    StitchingContext,
    InterventionBudget,
    SessionStatus,
    ClassificationResult,
    NON_INTERRUPTIBLE_TOOLS,
    INTERVENTION_PRIORITIES,
)
from .classifier import InterventionClassifier, get_intervention_classifier
from .debouncer import InterventionDebouncer

__all__ = [
    "GenerationState",
    "InterventionType",
    "InterventionSignal",
    "StitchingContext",
    "InterventionBudget",
    "SessionStatus",
    "ClassificationResult",
    "NON_INTERRUPTIBLE_TOOLS",
    "INTERVENTION_PRIORITIES",
    "InterventionClassifier",
    "get_intervention_classifier",
    "InterventionDebouncer",
]
