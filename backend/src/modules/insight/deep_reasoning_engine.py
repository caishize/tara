"""DeepReasoningEngine — L3 Sonnet deep analysis for cross-signal insights.

Handles ~20% of insights that benefit from deeper reasoning:
- Cross-entity insights (3+ entity types in signals)
- Trend alerts with low confidence
- Family climate / relationship diagnostics
- Long-term pattern correlation

Runs asynchronously via Celery after the main L1/L2 pipeline completes.
Uses Sonnet (via call_llm_raw) for richer analysis than Haiku.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from ...config.logging import get_logger
from ...config.settings import settings
from .insight_llm_client import call_llm_raw
from .models import (
    EntitySpec,
    GenerationLevel,
    InformationTier,
    InsightCandidate,
    InsightType,
)
from .insight_signal_collector import AllSignals

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# L3 eligibility criteria
# ---------------------------------------------------------------------------

# Minimum importance threshold for L3 candidates
_L3_MIN_IMPORTANCE = 60

# Minimum distinct entity types to qualify as "cross-entity"
_CROSS_ENTITY_TYPE_THRESHOLD = 3

# Insight types that always benefit from deep reasoning
_DEEP_ELIGIBLE_TYPES = frozenset({
    InsightType.FAMILY_CLIMATE.value,
    InsightType.RELATIONSHIP.value,
    InsightType.TREND_ALERT.value,
})

# Maximum L3 candidates per run (cost control)
_MAX_L3_CANDIDATES = 5

# Maximum content length for L3 insights
_L3_MAX_CONTENT_CHARS = 200


# ---------------------------------------------------------------------------
# System prompt for Sonnet deep reasoning
# ---------------------------------------------------------------------------

_DEEP_REASONING_SYSTEM_PROMPT = """\
你是一位资深家庭关系顾问，擅长从多维度信号中发现深层模式和关联。

## 任务
分析提供的家庭信号数据，生成深度洞察。你的分析应该：
1. 跨信号类型（事件、关系、记忆、承诺）寻找关联模式
2. 识别长期趋势和潜在风险
3. 提供具体、可操作的建议
4. 关注家庭成员之间的关系动态

## 输出格式
返回 JSON 数组，每个元素包含：
{
  "insight_type": "relationship|family_climate|trend_alert|efficiency|social_obligation",
  "title": "简短标题（≤20字）",
  "content": "深度分析内容（≤200字），包含跨信号关联发现",
  "importance": 60-100,
  "urgency": 0-100,
  "context_hint": "给用户的简短上下文提示（≤50字）",
  "suggested_action": "建议的下一步行动",
  "entities": [{"type": "person|event|trip", "id": "uuid", "role": "primary|related"}],
  "source_signal_ids": ["来源信号的标识符"],
  "source_context": {"analysis_type": "cross_signal|trend|climate"}
}

## 约束
- 每次最多返回3个洞察
- 只输出有高度置信的深层关联，不输出表面观察
- content 必须包含至少2个信号源的交叉分析
- 仅输出 JSON 数组，不要其他文字
"""


# ---------------------------------------------------------------------------
# DeepReasoningEngine
# ---------------------------------------------------------------------------


class DeepReasoningEngine:
    """L3 Sonnet-powered deep reasoning for cross-signal insight generation.

    Identifies candidates that benefit from deeper analysis, calls Sonnet
    for cross-signal correlation, and returns enriched InsightCandidates
    tagged with generation_level=L3_SONNET.
    """

    def __init__(self, target_date: date) -> None:
        self._target_date = target_date

    async def analyze(
        self,
        signals: AllSignals,
        existing_candidates: Optional[List[InsightCandidate]] = None,
    ) -> List[InsightCandidate]:
        """Run deep reasoning on signals that qualify for L3 analysis.

        Args:
            signals: All collected signals for the user.
            existing_candidates: L1/L2 candidates already generated
                (used to avoid duplicating their topics).

        Returns:
            List of L3 InsightCandidates with ``deep:`` dedup_key prefix.
        """
        if not self._qualifies_for_deep_analysis(signals, existing_candidates):
            logger.debug("Signals do not qualify for L3 deep reasoning")
            return []

        user_prompt = self._build_user_prompt(signals, existing_candidates)

        try:
            raw_response = await call_llm_raw(
                system_prompt=_DEEP_REASONING_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=settings.anthropic_model,
                max_tokens=1500,
            )
        except Exception as exc:
            logger.error("L3 deep reasoning LLM call failed: %s", exc)
            return []

        candidates = self._parse_response(raw_response)
        return candidates[:_MAX_L3_CANDIDATES]

    # ------------------------------------------------------------------
    # Eligibility check
    # ------------------------------------------------------------------

    def _qualifies_for_deep_analysis(
        self,
        signals: AllSignals,
        existing_candidates: Optional[List[InsightCandidate]],
    ) -> bool:
        """Check whether the signal set warrants L3 deep analysis."""
        # Need a minimum volume of signals
        if signals.total_count() < 3:
            return False

        # Check for cross-entity diversity
        if self._count_entity_types(signals) >= _CROSS_ENTITY_TYPE_THRESHOLD:
            return True

        # Check if existing candidates include deep-eligible types
        if existing_candidates:
            eligible_types = {
                c.insight_type for c in existing_candidates
                if c.insight_type in _DEEP_ELIGIBLE_TYPES
            }
            if eligible_types:
                return True

        # Check for relationship signals (always benefit from deeper analysis)
        if len(signals.relationships) >= 2:
            return True

        return False

    @staticmethod
    def _count_entity_types(signals: AllSignals) -> int:
        """Count distinct entity categories with data."""
        count = 0
        if signals.protected:
            count += 1
        if signals.events:
            count += 1
        if signals.relationships:
            count += 1
        if signals.memories:
            count += 1
        if signals.associations:
            count += 1
        if signals.graph:
            count += 1
        return count

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        signals: AllSignals,
        existing_candidates: Optional[List[InsightCandidate]],
    ) -> str:
        """Build the user prompt with signal data for Sonnet analysis."""
        sections: List[str] = [f"分析日期: {self._target_date.isoformat()}"]

        sections.append(self._format_signal_section(
            "事件信号", signals.events, max_items=10,
        ))
        sections.append(self._format_signal_section(
            "关系信号", signals.relationships, max_items=8,
        ))
        sections.append(self._format_signal_section(
            "记忆信号", signals.memories, max_items=5,
        ))
        sections.append(self._format_signal_section(
            "承诺/人情信号", signals.protected, max_items=5,
        ))
        sections.append(self._format_signal_section(
            "关联信号", signals.associations, max_items=5,
        ))
        sections.append(self._format_signal_section(
            "关系图谱信号", signals.graph, max_items=5,
        ))

        # Include existing L1/L2 topics to avoid duplication
        if existing_candidates:
            existing_topics = [
                f"- [{c.insight_type}] {c.title}"
                for c in existing_candidates[:10]
            ]
            sections.append(
                "已有洞察（避免重复这些主题）:\n" + "\n".join(existing_topics)
            )

        return "\n\n".join(s for s in sections if s)

    @staticmethod
    def _format_signal_section(
        label: str,
        items: List[Dict[str, Any]],
        max_items: int = 10,
    ) -> str:
        """Format a signal category into a prompt section."""
        if not items:
            return ""

        truncated = items[:max_items]
        # Serialize each item, stripping overly long values
        cleaned: List[Dict[str, Any]] = []
        for item in truncated:
            cleaned_item: Dict[str, Any] = {}
            for k, v in item.items():
                str_val = str(v)
                if len(str_val) > 200:
                    cleaned_item[k] = str_val[:200] + "..."
                else:
                    cleaned_item[k] = v
            cleaned.append(cleaned_item)

        return f"## {label} ({len(items)}条，展示{len(truncated)}条)\n{json.dumps(cleaned, ensure_ascii=False, default=str)}"

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw: str) -> List[InsightCandidate]:
        """Parse Sonnet JSON response into L3 InsightCandidates."""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("L3 deep reasoning returned non-JSON: %s", exc)
            return []

        if not isinstance(parsed, list):
            parsed = [parsed]

        candidates: List[InsightCandidate] = []
        for item in parsed:
            candidate = self._parse_single_item(item)
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _parse_single_item(self, item: Dict[str, Any]) -> Optional[InsightCandidate]:
        """Parse a single LLM output item into an L3 InsightCandidate."""
        try:
            importance = int(item.get("importance", 70))
            if importance < _L3_MIN_IMPORTANCE:
                logger.debug(
                    "L3 candidate below importance threshold: %d < %d",
                    importance, _L3_MIN_IMPORTANCE,
                )
                return None

            entity_specs = [
                EntitySpec(
                    entity_type=ent.get("type", "entity"),
                    entity_id=str(ent.get("id", "")),
                    role=ent.get("role", "related"),
                )
                for ent in item.get("entities", [])
            ]

            # Build source_context with deep analysis metadata
            source_context = dict(item.get("source_context", {}))
            source_context["_source"] = "deep_reasoning"
            signal_ids = item.get("source_signal_ids", [])
            if signal_ids:
                source_context["signal_ids"] = signal_ids

            content = str(item.get("content", ""))[:_L3_MAX_CONTENT_CHARS]
            insight_type = self._validate_insight_type(item.get("insight_type"))

            return InsightCandidate(
                insight_type=insight_type,
                title=str(item.get("title", ""))[:40],
                content=content,
                importance=_clamp(importance),
                urgency=_clamp(int(item.get("urgency", 50))),
                entities=entity_specs,
                source_context=source_context,
                suggested_action=item.get("suggested_action"),
                context_hint=str(item.get("context_hint", ""))[:80] or None,
                generation_level=GenerationLevel.L3_SONNET.value,
                information_tier=InformationTier.L2_FORMAL.value,
                dedup_key=f"deep:{insight_type}:{self._target_date.isoformat()}:{hashlib.md5(content.encode()).hexdigest()[:8]}",
            )
        except (TypeError, ValueError) as err:
            logger.warning("Skipping malformed L3 candidate: %s", err)
            return None

    @staticmethod
    def _validate_insight_type(raw_type: Optional[str]) -> str:
        """Validate insight_type against enum; fallback to RELATIONSHIP."""
        valid_types = frozenset(t.value for t in InsightType)
        if raw_type and raw_type in valid_types:
            return raw_type
        return InsightType.RELATIONSHIP.value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    """Clamp an integer to [lo, hi]."""
    return max(lo, min(hi, value))
