"""Memory System Configuration.

Centralized configuration for memory extraction, recall, and insight generation.
All hardcoded thresholds and parameters are now configurable.
"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemorySystemConfig(BaseSettings):
    """Configuration for the memory system."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== Memory Extraction ====================

    min_message_length: int = Field(
        default=10, description="Minimum message length for extraction"
    )
    extraction_temperature: float = Field(
        default=0.3, description="LLM temperature for extraction"
    )
    extraction_max_tokens: int = Field(
        default=1000, description="Max tokens for extraction"
    )
    llm_max_retries: int = Field(default=2, description="Max LLM retries")
    llm_retry_delay: float = Field(
        default=1.0, description="LLM retry delay (seconds)"
    )

    # ==================== Memory Recall ====================

    recall_default_limit: int = Field(default=5, description="Default recall limit")
    recall_max_limit: int = Field(default=100, description="Maximum recall limit")
    recall_per_location_limit: int = Field(
        default=3, description="Memories per location"
    )
    recall_per_person_limit: int = Field(default=3, description="Memories per person")
    recall_plan_limit: int = Field(default=3, description="Plan memories limit")
    recall_keyword_limit: int = Field(default=3, description="Keywords to search")
    recall_per_keyword_limit: int = Field(
        default=2, description="Memories per keyword"
    )
    recall_triggered_limit: int = Field(
        default=3, description="Triggered memories limit"
    )

    # ==================== Semantic Search ====================

    semantic_search_enabled: bool = Field(
        default=True, description="Enable semantic search"
    )
    semantic_similarity_threshold: float = Field(
        default=0.7, description="Semantic similarity threshold"
    )
    semantic_search_limit: int = Field(
        default=5, description="Semantic search results"
    )
    embedding_dimension: int = Field(default=1536, description="Embedding dimension")

    # ==================== Insight Generation ====================

    emotion_pattern_days: int = Field(
        default=7, description="Days for emotion pattern"
    )
    emotion_negative_threshold: int = Field(
        default=3, description="Negative emotion threshold"
    )
    old_plan_days: int = Field(default=14, description="Days before plan is old")
    upcoming_trip_days: int = Field(default=7, description="Days ahead for trips")

    # ==================== Insight Expiry ====================

    insight_safety_net_days: int = Field(
        default=90,
        description="Maximum days an insight lives before auto-expiry (safety net)",
    )

    # ==================== Insight Urgency Thresholds ====================

    trip_urgency_high_days: int = Field(
        default=3, description="Days for high urgency"
    )
    trip_same_day_priority: int = Field(
        default=9, description="Same-day trip priority"
    )
    trip_next_day_priority: int = Field(
        default=8, description="Next-day trip priority"
    )
    trip_upcoming_priority: int = Field(
        default=6, description="Upcoming trip priority"
    )

    # ==================== User Feedback ====================

    feedback_learning_enabled: bool = Field(
        default=True, description="Enable feedback learning"
    )
    feedback_dismiss_weight_decay: float = Field(
        default=0.1, description="Dismiss weight decay"
    )
    feedback_max_dismiss_count: int = Field(
        default=5, description="Max dismiss before suppress"
    )
    feedback_useful_weight_boost: float = Field(
        default=0.1, description="Useful weight boost"
    )
    insight_similarity_hours: int = Field(
        default=24, description="Hours for insight similarity"
    )

    # ==================== Trip Planning ====================

    trip_planning_max_memories: int = Field(
        default=15, description="Max memories for trip planning"
    )
    trip_planning_temperature: float = Field(
        default=0.5, description="Trip planning temperature"
    )
    trip_planning_max_tokens: int = Field(
        default=1500, description="Trip planning max tokens"
    )

    # ==================== Memory Compression ====================

    critical_tags: List[str] = Field(
        default=["health", "allergy", "birthday", "emergency_contact", "legal"],
        description="Tags that prevent memory compression",
    )
    compression_importance_threshold: int = Field(
        default=8,
        description="Memories with importance >= this are preserved",
    )
    compression_days_threshold: int = Field(
        default=7,
        description="Days before memories are eligible for compression",
    )
    compression_min_memories: int = Field(
        default=3,
        description="Minimum memories needed for compression",
    )
    compression_model: str = Field(
        default="",
        description="LLM model for memory compression (defaults to FAST_WORKER_MODEL if empty)",
    )
    compression_max_tokens: int = Field(
        default=500,
        description="Max tokens for compression summary",
    )

    # ==================== Memory Lifecycle ====================

    default_importance: int = Field(default=5, description="Default memory importance")
    default_confidence: float = Field(
        default=0.8, description="Default extraction confidence"
    )
    association_location_strength: float = Field(
        default=0.7, description="Location association strength"
    )
    association_person_strength: float = Field(
        default=0.7, description="Person association strength"
    )


# Global configuration instance
memory_config = MemorySystemConfig()


def get_memory_config() -> MemorySystemConfig:
    """Get the memory system configuration."""
    return memory_config


def reload_memory_config() -> MemorySystemConfig:
    """Reload configuration from environment (useful for testing)."""
    global memory_config
    memory_config = MemorySystemConfig()
    return memory_config
