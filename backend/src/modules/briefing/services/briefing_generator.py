"""
Briefing Generator - Generates secretary-style daily briefings with insights.

This module implements the BriefingGenerator class as specified in the
secretary-intelligence-enhancement design document. It generates daily briefings
that are ordered by importance (not chronologically) and include key insights,
opportunities, conflict resolutions, and relationship reminders.

Extracted from secretary/services/briefing_generator.py.
"""
import json
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ....config.logging import get_logger
from ....core.interfaces.llm_provider import LLMMessage
from ....core.utils.timezone import utc_now
from ....core.llm import openai_adapter
from ...curation.models import CuratedEvent
from ...curation.models import SocialIntent
from ...member.models.member import Member
from ...date_manager.models import ImportantDate
from ...curation.services.query_utils import escape_like

logger = get_logger(__name__)


# --- LLM Prompts ---

INSIGHT_GENERATION_PROMPT = """你是一位贴心的生活管家，像家里最操心的那个人，帮用户留意生活中容易忽略的事。

## 任务
基于今天的安排和过往记忆，生成2-3条最有价值的温馨提醒。

## 提醒类型

### 1. 人情冷暖
- "好久没和妈妈视频了，今天有空打个电话吧"
- "上次去上海见了老同学小王，这次又去了，看看TA最近怎么样？"
- "这是你第3次去北京了，上两次都去看了姑姑，这次也别忘了"

### 2. 生活关怀
- "明天降温，出门记得多穿点"
- "今天日程排得很满，中午记得吃饭，别又跳过了"
- "这周连续出差，回来好好休息一天"

### 3. 惦记着的事
- "你上个月说想带孩子去动物园，这周末要不要安排？"
- "你说过要给爸爸买个按摩椅，最近有空可以看看"

### 4. 人情往来
- "上次小李帮了大忙，找个机会好好谢谢人家"
- "下周是阿姨生日，提前准备份心意吧"

## 质量标准
1. 每条提醒必须是**具体的、温暖的、可执行的**
2. 洞察应该是**用户容易忽略但很重要的事**，特别是关系维护、健康关怀、家人陪伴
3. 语气像家人叮嘱，不要用"建议您"、"请确认"等公文词
4. 如果没有有价值的洞察，返回空列表
5. **禁止编造人名**：只能使用上下文中明确提供的人名，不能自己猜测或编造

## 输出格式
{
  "insights": [
    "好久没和妈妈聊了，今天有空打个电话吧",
    "下周是小王生日，趁今天有空准备份礼物"
  ]
}
"""


class BriefingItem(BaseModel):
    """Briefing item for a single event."""

    event_id: UUID
    title: str
    time_range: str
    priority_level: str
    priority_reason: str
    context_summary: str
    preparation_needed: Optional[str] = None


class ConflictBriefing(BaseModel):
    """Conflict briefing between two events."""

    conflict_id: str
    event1_id: UUID
    event2_id: UUID
    event1_title: str
    event2_title: str
    description: str
    resolution_suggestions: List[str] = Field(default_factory=list)


class GeneratorDailyBriefing(BaseModel):
    """Daily briefing output from the generator."""

    date: date
    key_insights: List[str] = []
    priority_items: List[BriefingItem] = []
    opportunities: List[str] = []
    conflicts: List[ConflictBriefing] = []
    relationship_reminders: List[str] = []


class BriefingGenerator:
    """Generates secretary-style daily briefings with LLM insights."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = openai_adapter
        from ...curation.services.conflict_detection import detect_conflicts
        self._detect_conflicts = detect_conflicts
        from ...insight.insight_context_assembler import InsightContextAssembler
        self._context_assembler = InsightContextAssembler(session)

    async def generate_daily_briefing(
        self,
        family_id: UUID,
        target_date: date,
    ) -> GeneratorDailyBriefing:
        """Generate a full daily briefing for the given date."""
        briefing = GeneratorDailyBriefing(date=target_date)

        events = await self._get_events_for_date(family_id, target_date)

        if not events:
            logger.info("No events found for %s", target_date)
            return briefing

        briefing.key_insights = await self._generate_key_insights(family_id, events)

        sorted_events = self._sort_by_importance(events)

        for event in sorted_events:
            item = await self._create_briefing_item(event, family_id)
            briefing.priority_items.append(item)

        briefing.opportunities = await self._discover_opportunities(family_id, events)
        briefing.conflicts = await self._check_conflicts_with_solutions(family_id, events)
        briefing.relationship_reminders = await self._generate_relationship_reminders(
            family_id, events
        )

        return briefing

    # ------------------------------------------------------------------
    # Event retrieval
    # ------------------------------------------------------------------

    async def _get_events_for_date(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[CuratedEvent]:
        """Get all active events for the given date."""
        try:
            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = datetime.combine(target_date, datetime.max.time())

            stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status.notin_(["cancelled", "completed"]),
                        or_(
                            and_(
                                CuratedEvent.normalized_start >= day_start,
                                CuratedEvent.normalized_start <= day_end,
                            ),
                            and_(
                                CuratedEvent.normalized_start <= day_start,
                                CuratedEvent.normalized_end >= day_start,
                            ),
                        ),
                    )
                )
                .order_by(CuratedEvent.normalized_start.asc())
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("Error getting events for date: %s", e)
            return []

    # ------------------------------------------------------------------
    # Importance sorting
    # ------------------------------------------------------------------

    def _sort_by_importance(self, events: List[CuratedEvent]) -> List[CuratedEvent]:
        """Sort events by four-dimension priority composite score."""
        from ...curation.services.priority_score import compute_priority_score

        def importance_score(event: CuratedEvent) -> float:
            # Use __dict__ to avoid triggering lazy load in async context
            association_count = len(event.__dict__.get("associations") or [])
            event_data = {
                "normalized_start": event.normalized_start,
                "event_type": event.event_type,
                "priority": event.priority,
                "association_count": association_count,
            }
            ps = compute_priority_score(event_data)
            return ps.composite

        return sorted(events, key=importance_score, reverse=True)

    # ------------------------------------------------------------------
    # Briefing item creation
    # ------------------------------------------------------------------

    async def _create_briefing_item(
        self,
        event: CuratedEvent,
        family_id: UUID,
    ) -> BriefingItem:
        """Create a briefing item for a single event."""
        time_range = "全天"
        if event.normalized_start:
            start_time = event.normalized_start.strftime("%H:%M")
            if event.normalized_end:
                end_time = event.normalized_end.strftime("%H:%M")
                time_range = f"{start_time}-{end_time}"
            else:
                time_range = start_time

        from ...curation.services.priority_score import compute_priority_score

        association_count = len(event.__dict__.get("associations") or [])
        ps = compute_priority_score({
            "normalized_start": event.normalized_start,
            "event_type": event.event_type,
            "priority": event.priority,
            "association_count": association_count,
        })
        priority_level = ps.priority_level
        priority_reason = self._analyze_priority(event)
        context_summary = await self._generate_context_summary(event, family_id)
        preparation_needed = self._generate_preparation_advice(event)

        return BriefingItem(
            event_id=event.id,
            title=event.title,
            time_range=time_range,
            priority_level=priority_level,
            priority_reason=priority_reason,
            context_summary=context_summary,
            preparation_needed=preparation_needed,
        )

    def _analyze_priority(self, event: CuratedEvent) -> str:
        """Analyze why an event has its priority level."""
        reasons = []

        if event.event_type in ["travel", "business_trip"]:
            reasons.append("出行计划")

        if event.event_type == "meeting":
            reasons.append("重要会议")

        if event.priority == "critical":
            reasons.append("高优先级")

        _assoc = event.__dict__.get("associations") or []
        if _assoc:
            reasons.append(f"关联{len(_assoc)}个事项")

        return "；".join(reasons) if reasons else "常规事项"

    async def _generate_context_summary(
        self,
        event: CuratedEvent,
        family_id: UUID,
    ) -> str:
        """Generate context summary for an event."""
        summaries = []

        if event.location:
            summaries.append(f"地点：{event.location}")

        _assoc = event.__dict__.get("associations") or []
        if _assoc:
            summaries.append(f"有{len(_assoc)}个相关事项")

        if not summaries:
            return "无特殊背景"

        return "；".join(summaries)

    def _generate_preparation_advice(self, event: CuratedEvent) -> Optional[str]:
        """Generate preparation advice for an event type."""
        advice_map = {
            "travel": "检查行李和证件",
            "business_trip": "检查行李和证件",
            "meeting": "准备会议材料",
            "appointment": "提前确认预约",
        }
        return advice_map.get(event.event_type)

    # ------------------------------------------------------------------
    # Key insights (LLM-powered)
    # ------------------------------------------------------------------

    async def _generate_key_insights(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[str]:
        """Generate key insights using LLM with rule-based fallback."""
        context = await self._collect_insight_context(family_id, events)

        if not context["events"] and not context["social_intents"]:
            return await self._generate_rule_based_insights(family_id, events)

        try:
            prompt = self._build_insight_prompt(context)

            # Use Haiku for per-insight text generation (cost-effective;
            # Sonnet-class models are reserved for full briefing summary).
            from ....core.llm.haiku_client import get_haiku_client
            from ....config.settings import settings as _settings

            haiku = get_haiku_client()
            haiku_response = await haiku.messages.create(
                model=_settings.fast_worker_model,
                max_tokens=500,
                temperature=0.3,
                system=INSIGHT_GENERATION_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            text_parts = [
                block.text for block in haiku_response.content
                if hasattr(block, "text")
            ]
            raw_text = text_parts[0].strip() if text_parts else ""

            insights = self._parse_insights(raw_text)
            return insights[:3]

        except Exception as e:
            logger.error("Error generating insights with LLM: %s", e)
            return await self._generate_rule_based_insights(family_id, events)

    async def _collect_insight_context(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> Dict[str, Any]:
        """Collect context needed for insight generation.

        Includes enriched context from InsightContextAssembler with
        PersonProfile data, memory summaries, and emotional trend.
        """
        context: Dict[str, Any] = {
            "events": [],
            "historical_events": [],
            "social_intents": [],
            "stale_contacts": [],
            "enriched_context": "",
        }

        # Extract person names and locations from events for enrichment
        person_names: List[str] = []
        locations: List[str] = []
        for event in events:
            context["events"].append({
                "title": event.title,
                "location": event.location,
                "event_type": event.event_type,
                "start_time": event.normalized_start.isoformat() if event.normalized_start else None,
            })
            if event.location:
                locations.append(event.location)
            # Extract person names from event tags/participants if available
            tags = getattr(event, "tags", None) or []
            for tag in tags:
                if isinstance(tag, str) and len(tag) <= 10:
                    person_names.append(tag)

        context["historical_events"] = await self._get_historical_events(family_id, events)
        context["social_intents"] = await self._get_triggered_intents(family_id, events)
        context["stale_contacts"] = await self._get_stale_contacts(family_id, events)

        # Enrich with PersonProfile/memory/emotional data
        if person_names or locations:
            try:
                # Get user_id from the first event's creator
                user_id = None
                for event in events:
                    uid = getattr(event, "user_id", None) or getattr(event, "created_by", None)
                    if uid:
                        user_id = uid
                        break
                if user_id:
                    enriched = await self._context_assembler.assemble(
                        user_id=user_id,
                        family_id=family_id,
                        person_names=person_names[:10] if person_names else None,
                        locations=locations[:5] if locations else None,
                    )
                    context["enriched_context"] = enriched.to_prompt_xml()
            except Exception as e:
                logger.debug("Context enrichment for briefing skipped: %s", e)

        return context

    async def _get_historical_events(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[Dict[str, Any]]:
        """Get related historical events for context."""
        historical = []

        for event in events:
            if event.location:
                try:
                    six_months_ago = utc_now() - timedelta(days=180)

                    stmt = (
                        select(CuratedEvent)
                        .where(
                            and_(
                                CuratedEvent.family_id == family_id,
                                CuratedEvent.location.ilike(f"%{escape_like(event.location)}%", escape="\\"),
                                CuratedEvent.normalized_start >= six_months_ago,
                                CuratedEvent.normalized_start < event.normalized_start,
                                CuratedEvent.is_active.is_(True),
                            )
                        )
                        .order_by(CuratedEvent.normalized_start.desc())
                        .limit(3)
                    )
                    result = await self.session.execute(stmt)
                    hist_events = list(result.scalars().all())

                    for hist_event in hist_events:
                        historical.append({
                            "title": hist_event.title,
                            "location": hist_event.location,
                            "date": hist_event.normalized_start.date().isoformat() if hist_event.normalized_start else None,
                        })
                except Exception as e:
                    logger.error("Error getting historical events: %s", e)

        return historical

    async def _get_triggered_intents(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[Dict[str, Any]]:
        """Get triggered social intents for today's events."""
        intents = []

        for event in events:
            if event.location:
                try:
                    stmt = (
                        select(SocialIntent)
                        .where(
                            and_(
                                SocialIntent.family_id == family_id,
                                SocialIntent.trigger_location.ilike(f"%{escape_like(event.location)}%", escape="\\"),
                                SocialIntent.status == "active",
                            )
                        )
                    )
                    result = await self.session.execute(stmt)
                    intent_list = list(result.scalars().all())

                    for intent in intent_list:
                        intents.append({
                            "person_name": intent.target_person_name,
                            "action": intent.action_description,
                            "location": intent.trigger_location,
                        })
                except Exception as e:
                    logger.error("Error getting social intents: %s", e)

        return intents

    async def _get_stale_contacts(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[Dict[str, Any]]:
        """Get contacts who haven't been in touch recently."""
        stale = []

        try:
            stmt = select(Member).where(Member.family_id == family_id)
            result = await self.session.execute(stmt)
            members = list(result.scalars().all())

            for event in events:
                if event.location:
                    for member in members:
                        member_loc = member.primary_location
                        if member_loc and member_loc in event.location:
                            stale.append({
                                "name": member.name,
                                "location": member_loc,
                            })
        except Exception as e:
            logger.error("Error getting stale contacts: %s", e)

        return stale[:5]

    def _build_insight_prompt(self, context: Dict[str, Any]) -> str:
        """Build the LLM prompt for insight generation."""
        prompt_parts = []

        if context["events"]:
            prompt_parts.append("## 今天的行程")
            for event in context["events"]:
                prompt_parts.append(f"- {event['title']} ({event['location']})")

        if context["historical_events"]:
            prompt_parts.append("\n## 历史记录")
            for hist in context["historical_events"]:
                prompt_parts.append(f"- {hist['date']}: {hist['title']} ({hist['location']})")

        if context["social_intents"]:
            prompt_parts.append("\n## 您之前提到的意图")
            for intent in context["social_intents"]:
                prompt_parts.append(f"- 去{intent['location']}要{intent['action']}{intent['person_name']}")

        if context["stale_contacts"]:
            prompt_parts.append("\n## 长时间未联系的人")
            for contact in context["stale_contacts"]:
                prompt_parts.append(f"- {contact['name']} ({contact['location']})")

        # Include enriched context (PersonProfiles, memory summaries, emotional trend)
        enriched = context.get("enriched_context", "")
        if enriched:
            prompt_parts.append(f"\n## 人物和记忆背景\n{enriched}")

        prompt_parts.append("\n请基于以上信息生成2-3条核心洞察。")

        return "\n".join(prompt_parts)

    def _parse_insights(self, llm_response: str) -> List[str]:
        """Parse LLM response into a list of insight strings."""
        try:
            data = json.loads(llm_response)
            if "insights" in data and isinstance(data["insights"], list):
                return data["insights"]
        except json.JSONDecodeError:
            lines = llm_response.strip().split("\n")
            insights = []
            for line in lines:
                line = line.strip()
                if line.startswith("-") or line.startswith("*"):
                    line = line[1:].strip()
                if line and len(line) > 10:
                    insights.append(line)
            return insights

        return []

    async def _generate_rule_based_insights(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[str]:
        """Generate rule-based insights (fallback when LLM unavailable)."""
        insights = []

        travel_events = [e for e in events if e.event_type in ["travel", "business_trip"]]

        for travel_event in travel_events:
            if travel_event.location:
                historical_insight = await self._generate_historical_insight(
                    family_id, travel_event.location
                )
                if historical_insight:
                    insights.append(historical_insight)

                intent_insight = await self._generate_intent_insight(
                    family_id, travel_event.location
                )
                if intent_insight:
                    insights.append(intent_insight)

        return insights[:3]

    async def _generate_historical_insight(
        self,
        family_id: UUID,
        location: str,
    ) -> Optional[str]:
        """Generate a historical insight for a location."""
        try:
            six_months_ago = utc_now() - timedelta(days=180)

            stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.location.ilike(f"%{escape_like(location)}%", escape="\\"),
                        CuratedEvent.normalized_start >= six_months_ago,
                        CuratedEvent.is_active.is_(True),
                    )
                )
                .order_by(CuratedEvent.normalized_start.desc())
                .limit(3)
            )
            result = await self.session.execute(stmt)
            historical_events = list(result.scalars().all())

            if historical_events:
                event_titles = [e.title for e in historical_events[:2]]
                return f"今天去{location}，上次您{event_titles[0]}，这次可能需要跟进"
        except Exception as e:
            logger.error("Error generating historical insight: %s", e)

        return None

    async def _generate_intent_insight(
        self,
        family_id: UUID,
        location: str,
    ) -> Optional[str]:
        """Generate a social-intent insight for a location."""
        try:
            stmt = (
                select(SocialIntent)
                .where(
                    and_(
                        SocialIntent.family_id == family_id,
                        SocialIntent.trigger_location.ilike(f"%{escape_like(location)}%", escape="\\"),
                        SocialIntent.status == "active",
                    )
                )
                .limit(1)
            )
            result = await self.session.execute(stmt)
            intent = result.scalar_one_or_none()

            if intent:
                person_name = intent.target_person_name or "某人"
                action = intent.action_description or "见面"
                return f"您之前提到去{location}要{action}{person_name}，这次可以安排"
        except Exception as e:
            logger.error("Error generating intent insight: %s", e)

        return None

    # ------------------------------------------------------------------
    # Opportunity discovery
    # ------------------------------------------------------------------

    async def _discover_opportunities(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[str]:
        """Discover opportunities from today's events."""
        opportunities = []

        # 1. Social intents triggered by event locations
        for event in events:
            if event.location:
                try:
                    stmt = (
                        select(SocialIntent)
                        .where(
                            and_(
                                SocialIntent.family_id == family_id,
                                SocialIntent.trigger_location.ilike(f"%{escape_like(event.location)}%", escape="\\"),
                                SocialIntent.status == "active",
                            )
                        )
                    )
                    result = await self.session.execute(stmt)
                    intents = list(result.scalars().all())

                    for intent in intents:
                        person_name = intent.target_person_name or "某人"
                        action = intent.action_description or "见面"
                        opportunities.append(f"顺便{action}{person_name}")
                except Exception as e:
                    logger.error("Error checking social intents: %s", e)

        # 2. Nearby important dates (7 days)
        for event in events:
            if event.normalized_start:
                nearby_dates = await self._find_nearby_important_dates(
                    family_id, event.normalized_start.date()
                )
                for imp_date in nearby_dates:
                    days_until = (imp_date.solar_date - event.normalized_start.date()).days
                    if days_until == 0:
                        time_desc = "今天"
                    elif days_until == 1:
                        time_desc = "明天"
                    elif days_until <= 3:
                        time_desc = f"{days_until}天后"
                    else:
                        time_desc = "下周"

                    opportunities.append(f"{time_desc}是{imp_date.title}，可以提前准备")

        # 3. Contacts in event locations
        for event in events:
            if event.location:
                try:
                    stmt = (
                        select(Member)
                        .where(
                            and_(
                                Member.family_id == family_id,
                                Member.locations.isnot(None),
                            )
                        )
                    )
                    result = await self.session.execute(stmt)
                    all_members = list(result.scalars().all())

                    matched = 0
                    for member in all_members:
                        member_loc = member.primary_location
                        if member_loc and event.location.lower() in member_loc.lower():
                            opportunities.append(f"顺便约见{member.name}")
                            matched += 1
                            if matched >= 3:
                                break
                except Exception as e:
                    logger.error("Error checking stale contacts: %s", e)

        # Deduplicate
        opportunities = list(dict.fromkeys(opportunities))

        return opportunities[:5]

    async def _find_nearby_important_dates(
        self,
        family_id: UUID,
        reference_date: date,
    ) -> List[ImportantDate]:
        """Find important dates within 7 days of the reference date."""
        try:
            end_date = reference_date + timedelta(days=7)

            stmt = (
                select(ImportantDate)
                .where(
                    and_(
                        ImportantDate.family_id == family_id,
                        ImportantDate.solar_date >= reference_date,
                        ImportantDate.solar_date <= end_date,
                    )
                )
                .limit(3)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("Error finding nearby important dates: %s", e)
            return []

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    async def _check_conflicts_with_solutions(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[ConflictBriefing]:
        """Detect time conflicts and generate resolution suggestions."""
        conflicts = []

        for i, event1 in enumerate(events):
            for event2 in events[i + 1:]:
                if self._has_time_conflict(event1, event2):
                    suggestions = [
                        f"调整{event1.title}的时间",
                        f"调整{event2.title}的时间",
                        "取消其中一个事件",
                    ]

                    conflict = ConflictBriefing(
                        conflict_id=f"conflict_{event1.id}_{event2.id}",
                        event1_id=event1.id,
                        event2_id=event2.id,
                        event1_title=event1.title,
                        event2_title=event2.title,
                        description=f"「{event1.title}」与「{event2.title}」时间重叠",
                        resolution_suggestions=suggestions,
                    )
                    conflicts.append(conflict)

        return conflicts

    def _has_time_conflict(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
    ) -> bool:
        """Check if two events have a time overlap."""
        if not event1.normalized_start or not event2.normalized_start:
            return False

        end1 = event1.normalized_end or (event1.normalized_start + timedelta(hours=1))
        end2 = event2.normalized_end or (event2.normalized_start + timedelta(hours=1))

        return event1.normalized_start < end2 and event2.normalized_start < end1

    # ------------------------------------------------------------------
    # Relationship reminders
    # ------------------------------------------------------------------

    async def _generate_relationship_reminders(
        self,
        family_id: UUID,
        events: List[CuratedEvent],
    ) -> List[str]:
        """Generate relationship reminders for contacts in event locations."""
        reminders = []

        try:
            stmt = select(Member).where(Member.family_id == family_id)
            result = await self.session.execute(stmt)
            members = list(result.scalars().all())

            for event in events:
                if event.location:
                    for member in members:
                        member_loc = member.primary_location
                        if member_loc and (
                            member_loc in event.location or
                            event.location in member_loc
                        ):
                            reminders.append(f"{member.name}在{event.location}，可以考虑见面")
        except Exception as e:
            logger.error("Error generating relationship reminders: %s", e)

        reminders = list(dict.fromkeys(reminders))

        return reminders[:3]
