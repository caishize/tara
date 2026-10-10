"""Sensitivity level classification for conversation memories.

The canonical implementation lives in ``models.py`` alongside
``SensitivityLevel``.  This module re-exports for convenience.
"""

from .models import (
    SensitivityLevel,
    classify_sensitivity,
    _flatten_entity_values,
    _FINANCIAL_PATTERNS,
    _MEDICAL_PATTERNS,
)

__all__ = [
    "SensitivityLevel",
    "classify_sensitivity",
    "_flatten_entity_values",
    "_FINANCIAL_PATTERNS",
    "_MEDICAL_PATTERNS",
]
