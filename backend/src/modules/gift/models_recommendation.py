"""Gift recommendation domain models.

SQLAlchemy models for the recommendation side of the gift module:
    - gift_recommendations: recommendation records with LLM-generated suggestions
    - gift_tasks: gift tasks with state machine lifecycle
    - gift_preferences: per-member gift preference learning
    - gift_history: gift giving history records
    - gift_conversation_context: conversation-extracted gift context
    - member_gift_memory: denormalized member gift summary cache
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func

from ...db.session import Base
from ...core.utils.timezone import utc_now
from .models_enums import GiftCategory, RecommendStatus, TaskStatus, TriggerSource


class GiftRecommendation(Base):
    """GiftRecommendation entity — LLM-generated gift suggestions."""

    __tablename__ = "gift_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient_member_id = Column(UUID(as_uuid=True), nullable=False)
    requester_user_id = Column(UUID(as_uuid=True), nullable=False)
    related_date_id = Column(UUID(as_uuid=True), nullable=True)

    occasion = Column(String(50), nullable=False)
    occasion_date = Column(Date, nullable=True)
    trigger_source = Column(String(50), nullable=False, default=TriggerSource.USER_REQUEST.value)

    budget_min = Column(Numeric(10, 2), nullable=True)
    budget_max = Column(Numeric(10, 2), nullable=True)
    user_preferences = Column(Text, nullable=True)

    recommendations = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default=RecommendStatus.PENDING.value)
    selected_option_index = Column(Integer, nullable=True)

    excluded_categories = Column(ARRAY(String), nullable=True)
    dedup_warnings = Column(JSONB, nullable=True)

    llm_prompt = Column(Text, nullable=True)
    llm_model = Column(String(100), nullable=True)
    generation_time_ms = Column(Integer, nullable=True)

    gift_type = Column(String(20), nullable=False, default="product")
    integration_status = Column(String(20), nullable=False, default="pending")
    shopping_item_id = Column(UUID(as_uuid=True), nullable=True)
    linked_shopping_item_id = Column(UUID(as_uuid=True), nullable=True)
    travel_plan_id = Column(UUID(as_uuid=True), nullable=True)
    purchase_status = Column(String(20), nullable=True)
    purchase_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    selected_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_recommendation_family", "family_id"),
        Index("idx_recommendation_recipient", "recipient_member_id"),
        Index("idx_recommendation_status", "status"),
        Index("idx_recommendation_occasion", "occasion"),
        Index("idx_recommendation_created", "created_at"),
        Index("idx_recommendation_gift_type", "gift_type"),
        Index("idx_recommendation_integration_status", "integration_status"),
        Index("idx_recommendation_shopping_item", "shopping_item_id"),
        Index("idx_recommendation_linked_shopping", "linked_shopping_item_id"),
    )

    def __repr__(self):
        return f"<GiftRecommendation(id={self.id}, recipient={self.recipient_member_id}, occasion={self.occasion})>"


class GiftTask(Base):
    """GiftTask entity — gift recommendation task state machine."""

    __tablename__ = "gift_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    important_date_id = Column(UUID(as_uuid=True), nullable=False)
    member_id = Column(UUID(as_uuid=True), nullable=False)

    occasion = Column(String(50), nullable=False)
    occasion_date = Column(Date, nullable=False)
    occasion_title = Column(String(200), nullable=True)

    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    trigger_source = Column(String(50), nullable=False, default=TriggerSource.AUTO_DATE.value)

    budget_min = Column(Integer, nullable=True)
    budget_max = Column(Integer, nullable=True)

    status = Column(String(50), nullable=False, default=TaskStatus.PENDING.value)

    recommendation_id = Column(UUID(as_uuid=True), nullable=True)
    recommendation_history = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_gift_task_family", "family_id"),
        Index("idx_gift_task_status", "status"),
        Index("idx_gift_task_scheduled", "scheduled_time"),
        Index("idx_gift_task_member", "member_id"),
        Index("idx_gift_task_date", "important_date_id"),
        Index("idx_gift_task_occasion_date", "occasion_date"),
        Index("idx_gift_task_unique_date_year", "important_date_id", "occasion_date", unique=True),
    )

    def __repr__(self):
        return f"<GiftTask(id={self.id}, occasion={self.occasion}, status={self.status})>"

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED.value

    @property
    def is_due(self) -> bool:
        return (
            self.status == TaskStatus.PENDING.value
            and self.scheduled_time <= utc_now()
        )


class GiftPreference(Base):
    """GiftPreference entity — per-member preference learning."""

    __tablename__ = "gift_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    member_id = Column(UUID(as_uuid=True), nullable=False)

    gift_category = Column(String(50), nullable=False)
    preference_score = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.5)
    source = Column(String(50), nullable=False)

    feedback_count = Column(Integer, nullable=False, default=0)
    positive_count = Column(Integer, nullable=False, default=0)
    negative_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_feedback_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_preference_family", "family_id"),
        Index("idx_preference_member", "member_id"),
        Index("idx_preference_category", "gift_category"),
        Index("idx_preference_member_category", "member_id", "gift_category", unique=True),
    )

    def __repr__(self):
        return f"<GiftPreference(member={self.member_id}, category={self.gift_category}, score={self.preference_score})>"


class GiftHistory(Base):
    """GiftHistory entity — gift giving history records."""

    __tablename__ = "gift_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    giver_user_id = Column(UUID(as_uuid=True), nullable=False)
    recipient_member_id = Column(UUID(as_uuid=True), nullable=False)
    recommendation_id = Column(UUID(as_uuid=True), nullable=True)
    related_date_id = Column(UUID(as_uuid=True), nullable=True)

    gift_name = Column(String(200), nullable=False)
    gift_category = Column(String(50), nullable=False)
    gift_description = Column(Text, nullable=True)

    occasion = Column(String(50), nullable=False)
    occasion_date = Column(Date, nullable=False)
    gift_price = Column(Text, nullable=True)  # Encrypted

    purchase_link = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)

    source = Column(String(50), nullable=False, default="manual")
    notes = Column(Text, nullable=True)

    feedback_rating = Column(String(20), nullable=True)
    feedback_text = Column(Text, nullable=True)
    feedback_collected_at = Column(DateTime(timezone=True), nullable=True)

    is_duplicate = Column(Boolean, nullable=False, default=False)
    similar_history_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_history_family", "family_id"),
        Index("idx_history_giver", "giver_user_id"),
        Index("idx_history_recipient", "recipient_member_id"),
        Index("idx_history_category", "gift_category"),
        Index("idx_history_occasion_date", "occasion_date"),
        Index("idx_history_created", "created_at"),
    )

    def __repr__(self):
        return f"<GiftHistory(id={self.id}, gift={self.gift_name}, recipient={self.recipient_member_id})>"


class GiftConversationContext(Base):
    """GiftConversationContext entity — conversation-extracted gift context."""

    __tablename__ = "gift_conversation_context"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    member_id = Column(UUID(as_uuid=True), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    recommendation_id = Column(UUID(as_uuid=True), nullable=True)

    context_type = Column(String(50), nullable=False)
    raw_text = Column(Text, nullable=False)
    extracted_value = Column(Text, nullable=True)
    extracted_data = Column(JSONB, nullable=True)
    affected_categories = Column(ARRAY(String(50)), nullable=True)

    sentiment = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=False, default=0.8)

    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(50), nullable=False, default="conversation")

    mentioned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_conv_ctx_family", "family_id"),
        Index("idx_conv_ctx_member", "member_id"),
        Index("idx_conv_ctx_type", "context_type"),
        Index("idx_conv_ctx_active", "is_active"),
        Index("idx_conv_ctx_mentioned", "mentioned_at"),
    )

    def __repr__(self):
        return f"<GiftConversationContext(id={self.id}, type={self.context_type}, member={self.member_id})>"


class MemberGiftMemory(Base):
    """MemberGiftMemory entity — denormalized member gift summary cache."""

    __tablename__ = "member_gift_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    member_id = Column(UUID(as_uuid=True), nullable=False, unique=True)

    total_gifts_received = Column(Integer, nullable=False, default=0)
    gifts_last_year = Column(Integer, nullable=False, default=0)
    gifts_last_3_years = Column(Integer, nullable=False, default=0)

    recent_gifts = Column(JSONB, nullable=True)
    category_counts = Column(JSONB, nullable=True)
    gifts_to_avoid = Column(JSONB, nullable=True)

    liked_categories = Column(ARRAY(String(50)), nullable=True)
    disliked_categories = Column(ARRAY(String(50)), nullable=True)
    brand_preferences = Column(JSONB, nullable=True)

    typical_price_min = Column(Float, nullable=True)
    typical_price_max = Column(Float, nullable=True)
    preference_scores = Column(JSONB, nullable=True)

    conversation_insights = Column(JSONB, nullable=True)
    interest_keywords = Column(ARRAY(String(100)), nullable=True)

    relationship_type = Column(String(50), nullable=True)
    intimacy_level = Column(Integer, nullable=True)
    special_notes = Column(Text, nullable=True)

    total_recommendations = Column(Integer, nullable=False, default=0)
    accepted_recommendations = Column(Integer, nullable=False, default=0)
    acceptance_rate = Column(Float, nullable=True)
    last_recommended_items = Column(JSONB, nullable=True)
    occasions_history = Column(JSONB, nullable=True)

    last_gift_date = Column(DateTime(timezone=True), nullable=True)
    last_recommendation_date = Column(DateTime(timezone=True), nullable=True)
    last_conversation_update = Column(DateTime(timezone=True), nullable=True)

    memory_richness_score = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_gift_memory_family", "family_id"),
        Index("idx_gift_memory_member", "member_id"),
        Index("idx_gift_memory_updated", "updated_at"),
    )

    def __repr__(self):
        return f"<MemberGiftMemory(member={self.member_id}, total_gifts={self.total_gifts_received})>"

    def calculate_richness_score(self) -> float:
        score = 0.0
        if self.total_gifts_received > 0:
            score += min(0.3, self.total_gifts_received * 0.05)
        if self.liked_categories:
            score += min(0.15, len(self.liked_categories) * 0.03)
        if self.preference_scores:
            score += min(0.10, len(self.preference_scores) * 0.02)
        if self.conversation_insights:
            insights = self.conversation_insights
            if insights.get("recent_mentions"):
                score += min(0.10, len(insights["recent_mentions"]) * 0.02)
            if insights.get("explicit_preferences"):
                score += min(0.10, len(insights["explicit_preferences"]) * 0.02)
            if insights.get("constraints"):
                score += 0.05
        if self.relationship_type:
            score += 0.05
        if self.intimacy_level:
            score += 0.05
        if self.special_notes:
            score += 0.1
        return min(1.0, score)
