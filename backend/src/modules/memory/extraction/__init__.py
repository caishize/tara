"""
Agentic Extraction Module - LLM-driven intent understanding and entity extraction.

This module replaces rule-based pattern matching with LLM-driven semantic understanding:
- UnifiedAgenticExtractor: Single LLM call for intent + entities + slots
- ExtractionCache: Three-layer caching for performance optimization
- Prompts: Prompt templates for extraction tasks
"""

from .unified_extractor import (
    UnifiedAgenticExtractor,
    ExtractionResult,
    ExtractedIntent,
    ExtractedEntities,
    ExtractedSlots,
    ExtractedRelationship,
    get_extractor,
    extract_all,
)
from .cache import ExtractionCache, get_extraction_cache

__all__ = [
    "UnifiedAgenticExtractor",
    "ExtractionResult",
    "ExtractedIntent",
    "ExtractedEntities",
    "ExtractedSlots",
    "ExtractedRelationship",
    "ExtractionCache",
    "get_extractor",
    "get_extraction_cache",
    "extract_all",
]
