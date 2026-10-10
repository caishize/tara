"""Preference extraction service (E2 Layer 2).

Analyzes accumulated PreferenceSignal records, extracts structured
UserPreferenceRule entries via batch Haiku calls, and manages rule lifecycle.

Rule lifecycle (encoded via existing is_active + status_note columns):
  - draft:    is_active=False, status_note contains "draft"
  - active:   is_active=True
  - archived: is_active=False, status_note contains "archived"

Dormant rules (draft) are re-evaluated when new matching signals arrive.
If accumulated confidence >= 0.6, they are promoted to active.

Runs as a daily Celery task (secretary.extract_preference_rules, 05:00).
"""
import json
import logging
from datetime import timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.settings import settings
from ....core.utils.timezone import utc_now
from ..models import PreferenceSignal, UserPreferenceRule

logger = logging.getLogger(__name__)

_MIN_SIGNALS_FOR_EXTRACTION = 3
_DEFAULT_RULE_TTL_DAYS = 90
_MAX_SIGNALS_PER_GROUP = 10
_DORMANT_PROMOTION_THRESHOLD = 0.6

_EXTRACTION_PROMPT = """<dismissal_signals>
{signals_text}
</dismissal_signals>

分析这些反馈信号的共同模式，提取一条用户偏好规则。

规则：
- 只提取有明确模式的规则，不要过度推断
- condition 中只包含在信号中反复出现的维度
- confidence 反映模式的一致性 (0.0-1.0)
- scope 为 "event_type" | "person" | "global"

输出 JSON:
{{
  "condition_event_type": "business_trip 或 null",
  "condition_suggestion_type": "social_meeting 或 null",
  "condition_person_id": "uuid 或 null",
  "condition_location": "地点 或 null",
  "action": "suppress 或 deprioritize",
  "confidence": 0.85,
  "explanation": "用户不希望在出差期间安排社交活动",
  "scope": "event_type",
  "ttl_days": 90
}}"""


class PreferenceExtractionService:
    """Extract structured preference rules from accumulated signals."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def extract_rules_for_user(self, user_id: UUID) -> List[UserPreferenceRule]:
        """Extract preference rules from unprocessed signals for a user.

        Before creating new rules, attempts to re-evaluate dormant (draft) rules
        that match incoming signals. If a dormant rule's recalculated confidence
        crosses the promotion threshold, it is promoted to active (TC-6).
        """
        groups = await self._group_unprocessed_signals(user_id)
        new_rules: List[UserPreferenceRule] = []

        for category_key, signals in groups.items():
            if len(signals) < _MIN_SIGNALS_FOR_EXTRACTION:
                continue

            # Step 1: Try to promote dormant rules matching these signals
            promoted = await self._try_promote_dormant_rules(
                user_id, category_key, signals,
            )
            if promoted:
                new_rules.extend(promoted)
                # Mark signals as processed — they contributed to promotion
                for signal in signals:
                    signal.processed = True
                continue

            # Step 2: No dormant rule matched — extract a new rule via LLM
            try:
                rule = await self._extract_via_llm(user_id, signals)
            except Exception as exc:
                logger.warning(
                    "LLM extraction failed for user %s category %s: %s",
                    user_id, category_key, exc,
                )
                continue

            if rule is not None:
                # Low confidence -> draft (inactive), wait for more signals
                if rule.confidence < _DORMANT_PROMOTION_THRESHOLD:
                    rule.is_active = False

                # Conflict resolution: keep higher confidence rule
                await self._resolve_conflicts(rule)

                self._session.add(rule)
                new_rules.append(rule)

            # Mark signals as processed regardless of extraction outcome
            for signal in signals:
                signal.processed = True

        if new_rules:
            logger.info(
                "Extracted %d preference rules for user %s", len(new_rules), user_id,
            )

        return new_rules

    async def extract_all_pending(self) -> int:
        """Extract rules for all users with pending signals. Returns total rules created."""
        stmt = (
            select(PreferenceSignal.user_id)
            .where(PreferenceSignal.processed.is_(False))
            .group_by(PreferenceSignal.user_id)
            .having(func.count() >= _MIN_SIGNALS_FOR_EXTRACTION)
        )
        result = await self._session.execute(stmt)
        user_ids = [row[0] for row in result.all()]

        total = 0
        for uid in user_ids:
            rules = await self.extract_rules_for_user(uid)
            total += len(rules)

        return total

    async def _group_unprocessed_signals(
        self, user_id: UUID
    ) -> Dict[str, List[PreferenceSignal]]:
        """Group unprocessed signals by category_key."""
        stmt = (
            select(PreferenceSignal)
            .where(
                and_(
                    PreferenceSignal.user_id == user_id,
                    PreferenceSignal.processed.is_(False),
                )
            )
            .order_by(PreferenceSignal.created_at)
        )
        result = await self._session.execute(stmt)
        signals = result.scalars().all()

        groups: Dict[str, List[PreferenceSignal]] = {}
        for signal in signals:
            groups.setdefault(signal.category_key, []).append(signal)
        return groups

    async def _extract_via_llm(
        self, user_id: UUID, signals: List[PreferenceSignal]
    ) -> Optional[UserPreferenceRule]:
        """Call Haiku to extract a structured preference rule from signals."""
        capped_signals = signals[:_MAX_SIGNALS_PER_GROUP]
        signals_text = "\n".join(
            f"{i + 1}. {s.created_at.strftime('%Y-%m-%d')}: "
            f"{s.signal_type} "
            f"(context: {json.dumps(s.source_context, ensure_ascii=False)})"
            for i, s in enumerate(capped_signals)
        )

        prompt = _EXTRACTION_PROMPT.format(signals_text=signals_text)

        try:
            from ....core.llm.haiku_client import get_haiku_client

            client = get_haiku_client()
            response = await client.messages.create(
                model=settings.fast_worker_model,
                max_tokens=200,
                system="你是用户行为模式分析专家。根据用户的反馈信号提取偏好规则。只输出JSON。",
                messages=[{"role": "user", "content": prompt}],
            )

            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if not text_parts:
                logger.warning("Empty response from Haiku during preference extraction")
                return None

            raw_text = text_parts[0].strip()
        except Exception as exc:
            logger.warning("LLM call failed during preference extraction: %s", exc)
            return None

        try:
            # Parse JSON from response (may be wrapped in ```json blocks)
            text = raw_text
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse LLM extraction response: %s", raw_text[:200])
            return None

        family_id = signals[0].family_id
        ttl_days = data.get("ttl_days", _DEFAULT_RULE_TTL_DAYS)

        # Parse condition_person_id safely
        raw_person_id = data.get("condition_person_id")
        condition_person_id = None
        if raw_person_id:
            try:
                condition_person_id = UUID(str(raw_person_id))
            except (ValueError, TypeError):
                pass

        # C7: Validate and clamp LLM return values
        _VALID_ACTIONS = {"suppress", "deprioritize"}
        _VALID_SCOPES = {"event_type", "person", "global"}

        action = data.get("action", "suppress")
        if action not in _VALID_ACTIONS:
            action = "suppress"

        scope = data.get("scope", "event_type")
        if scope not in _VALID_SCOPES:
            scope = "event_type"

        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        ttl_days = max(1, min(365, int(ttl_days)))

        return UserPreferenceRule(
            user_id=user_id,
            family_id=family_id,
            condition_event_type=data.get("condition_event_type"),
            condition_suggestion_type=data.get("condition_suggestion_type"),
            condition_person_id=condition_person_id,
            condition_location=data.get("condition_location"),
            action=action,
            confidence=confidence,
            explanation=data.get("explanation", ""),
            scope=scope,
            source_signal_count=len(signals),
            expires_at=utc_now() + timedelta(days=ttl_days),
            is_active=True,
        )

    async def _try_promote_dormant_rules(
        self,
        user_id: UUID,
        category_key: str,
        new_signals: List[PreferenceSignal],
    ) -> List[UserPreferenceRule]:
        """Try to promote dormant (draft) rules that match incoming signals.

        Queries inactive rules whose condition matches the category of incoming
        signals. If the combined signal count crosses _MIN_SIGNALS_FOR_EXTRACTION
        and recalculated confidence >= 0.6, the rule is promoted to active (TC-6).

        Returns list of promoted rules (empty if none promoted).
        """
        # Find dormant rules for this user — draft status
        stmt = select(UserPreferenceRule).where(
            and_(
                UserPreferenceRule.user_id == user_id,
                UserPreferenceRule.is_active.is_(False),
                UserPreferenceRule.confidence < _DORMANT_PROMOTION_THRESHOLD,
            )
        )
        result = await self._session.execute(stmt)
        dormant_rules = result.scalars().all()

        if not dormant_rules:
            return []

        promoted: List[UserPreferenceRule] = []

        for rule in dormant_rules:
            # Check if any signal in this group matches the rule's conditions
            if not self._rule_matches_category(rule, category_key):
                continue

            # Track reconfirmation count in a metadata pattern
            old_signal_count = rule.source_signal_count or 0
            new_total = old_signal_count + len(new_signals)

            if new_total < _MIN_SIGNALS_FOR_EXTRACTION:
                # Not enough signals yet — just bump the count
                rule.source_signal_count = new_total
                continue

            # Recalculate confidence: simple heuristic — each new signal
            # pushes confidence up proportionally
            new_confidence = min(
                1.0,
                rule.confidence + 0.05 * len(new_signals),
            )

            if new_confidence >= _DORMANT_PROMOTION_THRESHOLD:
                rule.is_active = True
                rule.confidence = new_confidence
                rule.source_signal_count = new_total
                rule.expires_at = utc_now() + timedelta(days=_DEFAULT_RULE_TTL_DAYS)
                logger.info(
                    "Promoted dormant rule %s for user %s "
                    "(confidence %.2f -> %.2f, signals %d -> %d)",
                    rule.id, user_id,
                    rule.confidence - 0.05 * len(new_signals),
                    new_confidence,
                    old_signal_count,
                    new_total,
                )
                promoted.append(rule)
            else:
                # Still below threshold — update counts for next time
                rule.confidence = new_confidence
                rule.source_signal_count = new_total

        return promoted

    @staticmethod
    def _rule_matches_category(
        rule: UserPreferenceRule, category_key: str,
    ) -> bool:
        """Check if a dormant rule's conditions align with a signal category.

        Category keys are typically formatted as ``{event_type}:{suggestion_type}``
        or just ``{event_type}``. We check if the rule's condition fields overlap.
        """
        parts = category_key.split(":", 1)
        event_part = parts[0] if parts else ""
        suggestion_part = parts[1] if len(parts) > 1 else ""

        if rule.condition_event_type and event_part:
            if rule.condition_event_type.lower() == event_part.lower():
                return True
        if rule.condition_suggestion_type and suggestion_part:
            if rule.condition_suggestion_type.lower() == suggestion_part.lower():
                return True
        # If rule has no typed conditions, it's a broad rule — match any
        if (
            not rule.condition_event_type
            and not rule.condition_suggestion_type
            and not rule.condition_person_id
            and not rule.condition_location
        ):
            return True
        return False

    async def _resolve_conflicts(self, new_rule: UserPreferenceRule) -> None:
        """Deactivate conflicting rules with lower confidence."""
        stmt = select(UserPreferenceRule).where(
            and_(
                UserPreferenceRule.user_id == new_rule.user_id,
                UserPreferenceRule.is_active.is_(True),
                UserPreferenceRule.condition_event_type == new_rule.condition_event_type,
                UserPreferenceRule.condition_suggestion_type == new_rule.condition_suggestion_type,
                UserPreferenceRule.condition_person_id == new_rule.condition_person_id,
                UserPreferenceRule.condition_location == new_rule.condition_location,
            )
        )
        result = await self._session.execute(stmt)
        existing_rules = result.scalars().all()

        for existing in existing_rules:
            if existing.confidence <= new_rule.confidence:
                existing.is_active = False
                logger.info(
                    "Deactivated conflicting rule %s (conf=%.2f) in favor of new (conf=%.2f)",
                    existing.id, existing.confidence, new_rule.confidence,
                )
