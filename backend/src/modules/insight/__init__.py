"""Insight module - unified proactive intelligence system.

Single pipeline for insight generation, feedback, adoption, cascade,
and hygiene — all backed by the `insights` + `insight_entities` tables.
"""

from .models import (
    FeedbackType,
    Insight,
    InsightEntity,
    InsightStatus,
    InsightType,
)

# Repositories and services are lazy-loaded to avoid circular imports.
# Import directly: from src.modules.insight.insight_pipeline import ...

__all__ = [
    # Models & Enums
    "Insight",
    "InsightEntity",
    "InsightStatus",
    "InsightType",
    "FeedbackType",
    # Settings
    "UserInsightSettings",
    "InsightSettingsRepository",
    # Repository (lazy)
    "InsightRepository",
    # Context assembly (lazy)
    "InsightContextAssembler",
    "InsightContext",
]

_LAZY_IMPORTS = {
    # Settings
    "UserInsightSettings": ".insight_settings_model",
    "InsightSettingsRepository": ".insight_settings_repository",
    # Repositories (lazy to break circular import with memory/models.py)
    "InsightRepository": ".insight_repository",
    # Context assembly
    "InsightContextAssembler": ".insight_context_assembler",
    "InsightContext": ".insight_context_assembler",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib
        mod = importlib.import_module(_LAZY_IMPORTS[name], __name__)
        value = getattr(mod, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
