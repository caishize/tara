"""Zero-LLM rule engine for high-certainty insights (L1 generation level).

Handles ~50% of insight generation with <100ms latency by applying
deterministic rules to collected signals. No LLM calls — pure logic.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .insight_signal_collector import AllSignals
from .models import (
    EntitySpec,
    GenerationLevel,
    InformationTier,
    InsightCandidate,
    InsightType,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Weather placeholder (future API integration)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WeatherSignal:
    """Placeholder for future weather API data."""

    target_date: date
    condition: Optional[str] = None       # e.g. "rain", "snow", "heat_wave"
    temperature_high: Optional[float] = None
    temperature_low: Optional[float] = None
    severity: Optional[str] = None        # "mild", "moderate", "severe"
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


class RuleEngineInsights:
    """Zero-LLM rule engine for high-certainty insights (L1 generation level).

    Generates deterministic insight candidates from collected signals and
    holiday infrastructure without any LLM calls.
    """

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
        signals: AllSignals,
        db: AsyncSession,
    ) -> List[InsightCandidate]:
        """Generate rule-based insights from collected signals.

        Note: seasonal/holiday obligations are now handled by the LLM path
        via holiday_signals.py in the signal collector. The rule engine
        focuses on deadline reminders, weather, and periodic admin tasks.
        """
        candidates: List[InsightCandidate] = []
        candidates.extend(self._deadline_reminders(signals))
        candidates.extend(await self._weather_insights(user_id, target_date, db))
        candidates.extend(self._periodic_admin_reminders(signals))
        return candidates

    # ------------------------------------------------------------------
    # Rule 1: Deadline reminders from protected commitments
    # ------------------------------------------------------------------

    def _deadline_reminders(self, signals: AllSignals) -> List[InsightCandidate]:
        """Generate urgent reminders for commitments approaching deadline."""
        now = utc_now()
        three_days = now + timedelta(days=3)
        candidates: List[InsightCandidate] = []

        for sig in signals.protected:
            if sig.get("signal_type") != "commitment":
                continue

            deadline_str = sig.get("deadline")
            if not deadline_str:
                continue

            from datetime import datetime
            try:
                deadline_dt = datetime.fromisoformat(deadline_str)
            except (ValueError, TypeError):
                continue

            if deadline_dt > three_days:
                continue

            commitment_id = sig.get("commitment_id", "")
            who = sig.get("who", "")
            what = sig.get("what", "")
            to_whom = sig.get("to_whom", "")
            days_left = max(0, (deadline_dt - now).days)

            entities: List[EntitySpec] = []
            if commitment_id:
                entities.append(EntitySpec(
                    entity_type="commitment",
                    entity_id=commitment_id,
                    role="source",
                ))

            candidates.append(InsightCandidate(
                insight_type=InsightType.TIME.value,
                title=f"承诺即将到期: {what}" if what else "承诺即将到期",
                content=self._build_deadline_content(who, what, to_whom, days_left),
                importance=80,
                urgency=90 if days_left <= 1 else 75,
                entities=entities,
                source_context={
                    "commitment_id": commitment_id,
                    "commitment_type": sig.get("commitment_type"),
                    "days_remaining": days_left,
                },
                dedup_key=f"commitment:{commitment_id}" if commitment_id else "",
                context_hint=f"还剩{days_left}天到期" if days_left > 0 else "今天到期",
                best_action_window="尽快处理" if days_left <= 1 else f"{days_left}天内",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L2_FORMAL.value,
            ))

        return candidates

    @staticmethod
    def _build_deadline_content(
        who: str, what: str, to_whom: str, days_left: int,
    ) -> str:
        parts: List[str] = []
        if who:
            parts.append(f"{who}")
        if what:
            parts.append(f"承诺的「{what}」")
        if to_whom:
            parts.append(f"(对{to_whom})")
        if days_left == 0:
            parts.append("今天到期")
        elif days_left == 1:
            parts.append("明天到期")
        else:
            parts.append(f"还有{days_left}天到期")
        return "".join(parts) if parts else "承诺即将到期"

    # ------------------------------------------------------------------
    # Rule 2: Weather care insights (via Haiku LLM judgment)
    # ------------------------------------------------------------------

    async def _weather_insights(
        self,
        user_id: UUID,
        target_date: date,
        db: AsyncSession,
    ) -> List[InsightCandidate]:
        """Fetch today's weather and let Haiku decide what (if anything) to remind."""
        try:
            from ..member.models.member import Member
            result = await db.execute(
                select(Member).where(Member.user_id == user_id).limit(1)
            )
            member = result.scalar_one_or_none()
            city = member.primary_location if member else None
            if not city:
                return []

            from ..briefing.weather_service import WeatherService
            weather = await WeatherService().get_weather(city=city)
        except Exception as e:
            logger.debug("Weather insight skipped (fetch): %s", e)
            return []

        # Build a compact weather summary for the LLM
        parts = [f"城市：{weather.location or city}"]
        parts.append(f"当前气温：{weather.temperature}°C")
        if weather.high_temp is not None:
            parts.append(f"今日最高：{weather.high_temp}°C")
        if weather.low_temp is not None:
            parts.append(f"今日最低：{weather.low_temp}°C")
        if weather.condition:
            parts.append(f"天气状况：{weather.condition}")
        if weather.wind:
            parts.append(f"风况：{weather.wind}")
        if weather.humidity:
            parts.append(f"湿度：{weather.humidity}")
        weather_summary = "，".join(parts)

        system_prompt = (
            "你是用户的家庭管家小秘，说话像家人之间的叮嘱：温暖、贴心、不啰嗦。\n"
            "根据今日天气数据，判断是否需要提醒用户注意天气。\n"
            "只在天气有实际影响时才生成提醒（如：大温差、降雨、高温、严寒、大风等）。"
            "天气平常时返回空数组 []，不要为普通晴天生成无意义提醒。\n\n"
            "若需要提醒，返回 JSON 数组，每条格式：\n"
            '{"title": "≤12字标题", "content": "≤60字贴心提醒", '
            '"urgency": 0-100, "importance": 0-100, '
            '"dedup_suffix": "一个区分本条提醒的短标识如rain/cold/heat/wind"}\n\n'
            "通常最多生成1-2条，urgency/importance 反映实际紧迫程度。"
        )
        user_prompt = f"今日天气数据（{target_date}）：{weather_summary}"

        try:
            from .insight_llm_client import call_llm_and_parse
            raw_candidates = await call_llm_and_parse(system_prompt, user_prompt)
        except Exception as e:
            logger.debug("Weather insight skipped (LLM): %s", e)
            return []

        date_tag = target_date.isoformat()
        candidates: List[InsightCandidate] = []
        for rc in raw_candidates:
            # call_llm_and_parse already builds InsightCandidate; patch weather-specific fields
            dedup_suffix = rc.source_context.get("dedup_suffix", "care") if rc.source_context else "care"
            candidates.append(dataclasses.replace(
                rc,
                insight_type=InsightType.WEATHER_CARE.value,
                dedup_key=f"weather:{dedup_suffix}:{date_tag}",
                context_hint=f"今日天气：{weather.condition or weather_summary}",
                best_action_window=rc.best_action_window or "出门前",
                generation_level=GenerationLevel.L2_HAIKU.value,
                information_tier=(
                    InformationTier.L2_FORMAL.value
                    if (rc.urgency or 0) >= 60
                    else InformationTier.L1_PASSIVE.value
                ),
            ))
        return candidates

    # ------------------------------------------------------------------
    # Rule 4: Periodic admin reminders from recurring events
    # ------------------------------------------------------------------

    def _positive_affirmations(
        self,
        recent_contacts: List[Dict[str, Any]],
        completed_commitments: List[Dict[str, Any]],
        family_events: List[Dict[str, Any]],
        today: date,
    ) -> List[InsightCandidate]:
        """Generate positive affirmation insights from positive behavioral signals.

        Targets 20-30% of total insight volume per design spec.
        Rules:
          1. Consistent contact (3+ mentions in 7 days) → warm relationship note
          2. Commitment completed on time → task completion kudos
          3. Family time (3+ family events in 7 days) → family bonding affirmation
        """
        # ISO week number used in dedup keys to prevent generating the same
        # affirmation every day without forgetting it between weeks.
        year, week_num, _ = today.isocalendar()
        week_tag = f"{year}W{week_num:02d}"

        candidates: List[InsightCandidate] = []

        # Rule 1: Consistent contact — person mentioned 3+ times recently
        for contact in recent_contacts:
            mention_count = contact.get("recent_mention_count", 0)
            if mention_count < 3:
                continue
            person_id = contact.get("person_id", "")
            person_name = contact.get("person_name", "")
            if not person_id or not person_name:
                continue

            candidates.append(InsightCandidate(
                insight_type=InsightType.POSITIVE_AFFIRMATION.value,
                title=f"和{person_name}联系频繁",
                content=f"你和{person_name}最近联系很频繁，关系很温暖",
                importance=40,
                urgency=20,
                entities=[
                    EntitySpec(
                        entity_type="person",
                        entity_id=person_id,
                        role="primary",
                    ),
                ],
                source_context={
                    "category": "consistent_contact",
                    "person_id": person_id,
                    "mention_count": mention_count,
                },
                context_hint=f"近7天已联系{mention_count}次",
                dedup_key=f"positive:contact:{person_id}:{week_tag}",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L1_PASSIVE.value,
            ))

        # Rule 2: Commitment completed on time
        for commitment in completed_commitments:
            commitment_id = commitment.get("commitment_id", "")
            title = commitment.get("what", "")
            if not commitment_id or not title:
                continue

            # Truncate title to keep insight content concise
            short_title = title[:20] + "…" if len(title) > 20 else title
            candidates.append(InsightCandidate(
                insight_type=InsightType.POSITIVE_AFFIRMATION.value,
                title="承诺按时完成",
                content=f"你按时完成了「{short_title}」，很棒！",
                importance=35,
                urgency=15,
                entities=[
                    EntitySpec(
                        entity_type="commitment",
                        entity_id=commitment_id,
                        role="source",
                    ),
                ],
                source_context={
                    "category": "commitment_completed",
                    "commitment_id": commitment_id,
                },
                context_hint="按时完成承诺",
                dedup_key=f"positive:commitment:{commitment_id}",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L0_AUTO.value,
            ))

        # Rule 3: Family time — 3+ family-tagged events in the past 7 days
        _FAMILY_EVENT_TYPES = frozenset({
            "family_time", "family_meal", "family_activity",
            "family_outing", "family_event",
        })
        family_count = sum(
            1 for ev in family_events
            if ev.get("event_type", "") in _FAMILY_EVENT_TYPES
        )
        if family_count >= 3:
            candidates.append(InsightCandidate(
                insight_type=InsightType.POSITIVE_AFFIRMATION.value,
                title="家庭时间充足",
                content="本周家庭时间充足，你们在一起的时光很珍贵",
                importance=40,
                urgency=10,
                entities=[],
                source_context={
                    "category": "family_time",
                    "family_event_count": family_count,
                    "week": week_tag,
                },
                context_hint=f"本周已有{family_count}次家庭活动",
                dedup_key=f"positive:family_time:{week_tag}",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L1_PASSIVE.value,
            ))

        return candidates

    def _periodic_admin_reminders(
        self, signals: AllSignals,
    ) -> List[InsightCandidate]:
        """Generate life-admin reminders from upcoming curated events."""
        candidates: List[InsightCandidate] = []
        now = utc_now()

        for sig in signals.events:
            event_type = sig.get("event_type", "")
            if event_type not in (
                "medical_check", "bill_payment", "subscription_renewal",
                "insurance", "document_renewal", "vehicle_maintenance",
            ):
                continue

            start_str = sig.get("start")
            if not start_str:
                continue

            from datetime import datetime
            try:
                start_dt = datetime.fromisoformat(start_str)
            except (ValueError, TypeError):
                continue

            days_until = max(0, (start_dt - now).days)
            if days_until > 14:
                continue

            event_id = sig.get("event_id", "")
            title = sig.get("title", "待办事项")

            entities: List[EntitySpec] = []
            if event_id:
                entities.append(EntitySpec(
                    entity_type="event",
                    entity_id=event_id,
                    role="source",
                ))

            candidates.append(InsightCandidate(
                insight_type=InsightType.LIFE_ADMIN.value,
                title=f"事务提醒: {title}",
                content=f"「{title}」即将到期，请及时处理",
                importance=60,
                urgency=70 if days_until <= 3 else 50,
                entities=entities,
                source_context={
                    "event_id": event_id,
                    "event_type": event_type,
                    "days_until": days_until,
                },
                dedup_key=f"admin:{event_id}" if event_id else "",
                context_hint=f"还有{days_until}天" if days_until > 0 else "今天到期",
                best_action_window=(
                    "尽快" if days_until <= 1 else f"{days_until}天内"
                ),
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=(
                    InformationTier.L2_FORMAL.value
                    if days_until <= 3
                    else InformationTier.L1_PASSIVE.value
                ),
            ))

        return candidates
