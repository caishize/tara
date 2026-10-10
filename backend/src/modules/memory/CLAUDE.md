# Memory

## Purpose
Long-term memory system — extracts structured memories from conversations, compresses old entries, provides semantic + FTS hybrid recall, manages GraphRAG relationships, embeddings, and secretary notes.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, ..member.interface
- **Forbidden imports**: ai_engine.*, api.*, ..insight.services (use `__getattr__` lazy import)

## Key Files
| File | Purpose |
|------|---------|
| extraction/unified_extractor.py | LLM-based memory extraction from conversation turns |
| recall_service.py | Semantic + FTS hybrid recall with token budget |
| compression_service.py | Daily compression of old memories (Celery: 04:30) |
| embedding_service.py | Vector embedding generation and similarity search |
| graph_rag.py | GraphRAG relationship graph queries |
| consolidation_service.py | Merges duplicate/overlapping memories |
| emotional_trend_service.py | Tracks emotional patterns over time |
| secretary_note_service.py | Curated secretary notes (L1 context) |
| commitment_service.py | Tracks user commitments extracted from chat |
| sensitivity_classifier.py | Classifies memory sensitivity levels |
| tasks.py | Celery tasks: `secretary.post_session_reflection`, compression |

## Module Conventions
- Circular dependency with insight resolved via `__getattr__` lazy import in `__init__.py`
- Recall returns results within token budget (configurable)
- Compression runs daily at 04:30 UTC via Celery beat
- Memory types: fact, preference, event, emotion, commitment, relationship
- `bridge.py` provides cross-module access patterns
