"""PrepChainEngine -- rule-based preparation chain generator.

Given a target date and a list of upcoming event signals, generates
InsightCandidate objects for preparation steps that are due today.

Each event category has a fixed chain of PrepSteps with lead-day offsets.
When ``target_date`` matches a step's due date (event_date - lead_days),
the engine emits an InsightCandidate with pre-filled action_options,
context_hint, and dedup_key.

Zero LLM calls -- pure rule engine (GenerationLevel.L1_RULE).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .models import EntitySpec, GenerationLevel, InformationTier, InsightCandidate


# ---------------------------------------------------------------------------
# PrepStep definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrepStep:
    """Single step in a preparation chain."""

    title: str
    lead_days: int       # Days before event
    insight_type: str
    importance: int
    action_label: str
    urgency_base: int = 60


# ---------------------------------------------------------------------------
# Chain templates by event category
# ---------------------------------------------------------------------------

PREP_CHAINS: Dict[str, Tuple[PrepStep, ...]] = {
    "social_gathering": (
        PrepStep("交通规划", 0, "time", 80, "查看路线", 85),
        PrepStep("人物回顾", 0, "relationship", 60, "查看关系", 50),
        PrepStep("话题准备", 1, "efficiency", 50, "准备话题", 40),
        PrepStep("礼物/着装准备", 2, "life_admin", 70, "准备物品", 55),
    ),
    "family_trip": (
        PrepStep("天气查询", 1, "weather_care", 70, "查看天气", 60),
        PrepStep("行李清单", 2, "life_admin", 75, "检查清单", 65),
        PrepStep("预订确认", 3, "time", 80, "确认预订", 75),
        PrepStep("证件检查", 7, "life_admin", 85, "检查证件", 70),
    ),
    "important_date": (
        PrepStep("发送祝福", 0, "social_obligation", 80, "发送祝福", 90),
        PrepStep("安排提醒", 3, "time", 70, "安排行程", 60),
        PrepStep("购买提醒", 7, "life_admin", 75, "去购买", 55),
        PrepStep("礼物建议", 14, "favor", 60, "挑选礼物", 40),
    ),
    "commitment_deadline": (
        PrepStep("到期提醒", 0, "time", 90, "立即处理", 95),
        PrepStep("完成提醒", 1, "time", 80, "今天完成", 85),
        PrepStep("进展确认", 3, "efficiency", 60, "检查进度", 50),
    ),
    "business_meeting": (
        PrepStep("会议准备", 0, "efficiency", 75, "查看议程", 80),
        PrepStep("资料准备", 1, "efficiency", 70, "准备资料", 60),
        PrepStep("参会人回顾", 1, "relationship", 55, "了解与会者", 45),
    ),
}

# CuratedEvent.event_type -> chain key
_EVENT_TYPE_TO_CHAIN: Dict[str, str] = {
    "travel": "family_trip",
    "business_trip": "business_meeting",
    "meeting": "business_meeting",
    "appointment": "social_gathering",
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PrepChainEngine:
    """Generates preparation step insights for upcoming events."""

    def generate_for_date(
        self,
        target_date: datetime,
        events: List[Dict[str, Any]],
    ) -> List[InsightCandidate]:
        """Check all events against prep chain templates, return due steps."""
        candidates: List[InsightCandidate] = []
        for event in events:
            chain_key = self._classify_event(event)
            if chain_key is None:
                continue
            chain = PREP_CHAINS[chain_key]
            event_date = self._parse_event_date(event)
            if event_date is None:
                continue
            for step in chain:
                step_date = (event_date - timedelta(days=step.lead_days)).date()
                target_d = target_date.date() if isinstance(target_date, datetime) else target_date
                if step_date == target_d:
                    candidates.append(
                        self._build_candidate(event, step, chain_key)
                    )
        return candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_event(event: Dict[str, Any]) -> Optional[str]:
        """Map event to a prep chain template key."""
        # Important-date and commitment overrides take priority
        if event.get("important_date_id") or event.get("is_important_date"):
            return "important_date"
        if event.get("commitment_id") or event.get("is_commitment_deadline"):
            return "commitment_deadline"

        event_type = event.get("event_type", "")
        return _EVENT_TYPE_TO_CHAIN.get(event_type)

    @staticmethod
    def _parse_event_date(event: Dict[str, Any]) -> Optional[datetime]:
        """Extract event date from signal dict."""
        date_val = (
            event.get("normalized_start")
            or event.get("start")
            or event.get("date")
            or event.get("start_date")
        )
        if isinstance(date_val, datetime):
            return date_val
        if isinstance(date_val, str):
            try:
                return datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        return None

    @staticmethod
    def _build_candidate(
        event: Dict[str, Any],
        step: PrepStep,
        chain_key: str,
    ) -> InsightCandidate:
        """Build InsightCandidate for a due prep step."""
        event_title = event.get("title", "事件")
        title = f"{event_title}: {step.title}"[:200]
        content = f"距离「{event_title}」还有{step.lead_days}天，建议现在{step.title}"

        entities: List[EntitySpec] = []
        if event.get("event_id") or event.get("id"):
            eid = str(event.get("event_id") or event["id"])
            entities.append(
                EntitySpec(entity_type="event", entity_id=eid, role="primary")
            )
        if event.get("trip_id"):
            entities.append(
                EntitySpec(
                    entity_type="trip",
                    entity_id=str(event["trip_id"]),
                    role="related",
                )
            )

        event_id_str = str(event.get("event_id") or event.get("id", ""))

        return InsightCandidate(
            insight_type="prep_chain",
            title=title,
            content=content,
            importance=step.importance,
            urgency=step.urgency_base,
            entities=entities,
            source_context={
                "chain_type": chain_key,
                "step_title": step.title,
                "lead_days": step.lead_days,
                "event_id": event_id_str,
                "has_prep_chain": True,
            },
            context_hint=f"这是「{event_title}」预案链的一环",
            best_action_window=(
                "今天" if step.lead_days == 0 else "今天到明天"
            ),
            generation_level=GenerationLevel.L1_RULE.value,
            information_tier=InformationTier.L2_FORMAL.value,
            action_options=[
                {"type": "create_pending_action", "label": step.action_label},
                {"type": "open_detail", "label": "查看完整准备清单"},
                {"type": "defer", "label": "稍后提醒"},
            ],
            dedup_key=f"prep:{chain_key}:{event_id_str}:{step.title}",
        )
