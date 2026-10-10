"""Emotional Trend Service - Compute emotional trends from extracted sentiment values.

Tier 2 of the emotion understanding system (optimization doc 3.6).
Aggregates sentiment data from conversation_memories to determine
the user's emotional trajectory over a configurable time window.

No extra LLM calls -- purely DB aggregation over the sentiment field
persisted by Tier 1 (MEMORY_EXTRACTION_PROMPT).
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, case, literal
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .models import ConversationMemory, MemoryStatus, MemoryType

logger = get_logger(__name__)


@dataclass(frozen=True)
class EmotionalTrend:
    """Result of emotional trend computation."""

    trend: str  # "declining" | "improving" | "stable" | "unknown"
    negative_count: int
    positive_count: int
    neutral_count: int
    total_count: int
    suggested_tone: str  # "empathetic" | "encouraging" | "neutral"

    def to_prompt_section(self) -> str:
        """Format as a system prompt section for agent injection."""
        if self.trend == "unknown":
            return ""

        tone_labels = {
            "empathetic": "温和共情",
            "encouraging": "积极鼓励",
            "neutral": "平和自然",
        }
        tone_label = tone_labels.get(self.suggested_tone, "平和自然")

        return (
            f"## 用户近期情绪状态\n"
            f"最近7天情绪趋势: {self.trend}\n"
            f"负面情绪记忆: {self.negative_count} 条\n"
            f"正面情绪记忆: {self.positive_count} 条\n"
            f"建议回复语气: {tone_label}"
        )


async def compute_emotional_trend(
    session: AsyncSession,
    user_id: UUID,
    window_days: int = 7,
) -> EmotionalTrend:
    """Compute the user's emotional trend from extracted sentiment values.

    Queries conversation_memories for emotion/work types within the window,
    counts positive vs negative sentiment, and determines trend direction.

    Rules:
    - negative >= 3 AND negative > positive * 2 -> declining
    - positive >= 3 AND positive > negative * 2 -> improving
    - otherwise -> stable
    - no data -> unknown

    Args:
        session: Async DB session.
        user_id: The user to compute trend for.
        window_days: Number of days to look back.

    Returns:
        EmotionalTrend with counts and suggested tone.
    """
    since = utc_now() - timedelta(days=window_days)

    # Count sentiments in a single query using conditional aggregation
    query = select(
        func.count(ConversationMemory.id).label("total"),
        func.sum(
            case(
                (ConversationMemory.entities["sentiment"].astext == "negative", 1),
                else_=0,
            )
        ).label("negative_count"),
        func.sum(
            case(
                (ConversationMemory.entities["sentiment"].astext == "positive", 1),
                else_=0,
            )
        ).label("positive_count"),
        func.sum(
            case(
                (
                    or_(
                        ConversationMemory.entities["sentiment"].astext == "neutral",
                        ConversationMemory.entities["sentiment"].astext == "mixed",
                    ),
                    1,
                ),
                else_=0,
            )
        ).label("neutral_count"),
    ).where(
        and_(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.created_at >= since,
            or_(
                ConversationMemory.memory_type == MemoryType.EMOTION.value,
                ConversationMemory.memory_type == MemoryType.WORK.value,
            ),
            ConversationMemory.entities.has_key("sentiment"),
        )
    )

    try:
        result = await session.execute(query)
        row = result.one()
    except Exception as e:
        logger.error("Failed to compute emotional trend: %s", e)
        return EmotionalTrend(
            trend="unknown",
            negative_count=0,
            positive_count=0,
            neutral_count=0,
            total_count=0,
            suggested_tone="neutral",
        )

    total = row.total or 0
    negative = row.negative_count or 0
    positive = row.positive_count or 0
    neutral = row.neutral_count or 0

    if total == 0:
        return EmotionalTrend(
            trend="unknown",
            negative_count=0,
            positive_count=0,
            neutral_count=0,
            total_count=0,
            suggested_tone="neutral",
        )

    trend = _determine_trend(negative, positive)
    suggested_tone = _determine_tone(trend, negative, positive)

    return EmotionalTrend(
        trend=trend,
        negative_count=negative,
        positive_count=positive,
        neutral_count=neutral,
        total_count=total,
        suggested_tone=suggested_tone,
    )


def _determine_trend(negative: int, positive: int) -> str:
    """Determine trend direction from sentiment counts."""
    if negative >= 3 and negative > positive * 2:
        return "declining"
    if positive >= 3 and positive > negative * 2:
        return "improving"
    return "stable"


def _determine_tone(trend: str, negative: int, positive: int) -> str:
    """Determine suggested response tone based on trend."""
    if trend == "declining":
        return "empathetic"
    if trend == "improving":
        return "encouraging"
    return "neutral"
