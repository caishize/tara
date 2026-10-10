"""Memory module - the secretary's brain.

Extracts knowledge from conversations, builds the family knowledge base,
and supports cross-temporal associations.
"""

from .models import (
    ConversationMemory,
    MemoryAssociation,
    MemoryStatus,
    MemorySummary,
    MemoryType,
    SensitivityLevel,
    SummaryType,
    classify_sensitivity,
)
from .secretary_note_model import SecretaryNote, NoteCategory, NoteLifeType, NoteStatus
from .config import MemorySystemConfig, get_memory_config, memory_config

# Services with heavy dependencies are lazy-loaded.
# Import directly: from src.modules.memory.extraction_service import ...

__all__ = [
    # Models & Enums
    "ConversationMemory",
    "MemoryAssociation",
    "MemorySummary",
    "MemoryType",
    "MemoryStatus",
    "SensitivityLevel",
    "SummaryType",
    # Sensitivity classification
    "classify_sensitivity",
    # Secretary Notes
    "SecretaryNote",
    "NoteCategory",
    "NoteLifeType",
    "NoteStatus",
    # Config
    "MemorySystemConfig",
    "get_memory_config",
    "memory_config",
    # Repository
    "MemoryRepository",
    # Graph RAG
    "LightweightGraphRAG",
    # Services (lazy)
    "MemoryExtractionService",
    "MemoryExtractionServiceAsync",
    "MemoryRecallService",
    "ContextAwareRecallService",
    "MemoryConsolidationService",
    "MemoryCompressionService",
    "CompressionResult",
    "EmbeddingService",
    "get_embedding_service",
    "MemoryBridge",
    "SecretaryNoteService",
    "TransientFactManager",
    "FactVerificationGate",
    "NoteCandidate",
    "VerificationAction",
    "VerificationResult",
    # Commitment service (lazy)
    "CommitmentType",
    "SocialIntentType",
    "CommitmentStatus",
    "SocialIntentResult",
    "CommitmentItem",
    "SocialIntentParser",
    "CommitmentPreFilter",
    "VagueCommitmentTracker",
    # Emotional trend
    "EmotionalTrend",
    "compute_emotional_trend",
]

_LAZY_IMPORTS = {
    "MemoryExtractionService": ".extraction_service",
    "MemoryExtractionServiceAsync": ".extraction_service",
    "MemoryRecallService": ".recall_service",
    "ContextAwareRecallService": ".recall_service",
    "MemoryConsolidationService": ".consolidation_service",
    "MemoryCompressionService": ".compression_service",
    "CompressionResult": ".compression_service",
    "EmbeddingService": ".embedding_service",
    "get_embedding_service": ".embedding_service",
    "MemoryBridge": ".bridge",
    "SecretaryNoteService": ".secretary_note_service",
    "TransientFactManager": ".secretary_note_service",
    "FactVerificationGate": ".fact_verification",
    "NoteCandidate": ".fact_verification",
    "VerificationAction": ".fact_verification",
    "VerificationResult": ".fact_verification",
    # Commitment service
    "CommitmentType": ".commitment_service",
    "SocialIntentType": ".commitment_service",
    "CommitmentStatus": ".commitment_service",
    "SocialIntentResult": ".commitment_service",
    "CommitmentItem": ".commitment_service",
    "SocialIntentParser": ".commitment_service",
    "CommitmentPreFilter": ".commitment_service",
    "VagueCommitmentTracker": ".commitment_service",
    # Emotional trend
    "EmotionalTrend": ".emotional_trend_service",
    "compute_emotional_trend": ".emotional_trend_service",
    # Graph RAG
    "LightweightGraphRAG": ".graph_rag",
    # Repository — lazy to avoid circular import via InsightRepository base class
    "MemoryRepository": ".repository",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib
        mod = importlib.import_module(_LAZY_IMPORTS[name], __name__)
        value = getattr(mod, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
