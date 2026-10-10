"""Association discovery methods for the curation service.

Contains LLM-based and rule-engine association discovery,
merging, dedup, and quality filtering.
"""
import json
from copy import copy
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import make_transient

from ....config.logging import get_logger
from ....config.settings import settings
from ....core.interfaces.llm_provider import LLMMessage
from ....core.llm.haiku_client import get_haiku_client
from ....core.utils.timezone import get_user_timezone, utc_now
from ....modules.conversation.display_builder import build_display_data
from ..models import CuratedEvent, EventAssociation, UserPreferenceRule
from ..schemas import (
    LLMAssociationResponse,
    AssociationPriority,
    AssociationType,
    TargetType,
)
from .prompts import (
    ENHANCED_ASSOCIATION_PROMPT,
    DEFAULT_LLM_TEMPERATURE,
)
from .association_text import looks_internal_language

# --- PendingAction flood-control constants ---
_SUGGEST_ACTION_MAX_PENDING: int = 3       # max simultaneous unhandled suggest_* per user
_SUGGEST_ACTION_COOLDOWN_DAYS: int = 7     # cooldown: same user+target+type within N days
_SUGGEST_MEETING_CONFIDENCE_THRESHOLD: float = 0.7   # min confidence to escalate to suggest_meeting
_SUGGEST_GREETING_DAYS_THRESHOLD: int = 60           # min days_since_contact to escalate greeting
_SUGGEST_GREETING_DEPARTURE_DAYS: int = 7            # event must start within N days
_SUGGEST_REJECT_SUPPRESS_DAYS: int = 30               # suppress same target+type after user reject
_HAIKU_DRAFT_MAX_TOKENS: int = 150                    # draft messages are short
_SUGGEST_MEETING_ALLOWED_TEMPS: frozenset = frozenset({"cold", "cool"})

logger = get_logger(__name__)


class CurationAssociationMixin:
    """Mixin providing association discovery methods for SecretaryCurationService."""

    async def _discover_associations(
        self,
        family_id: UUID,
        curated_events: List[CuratedEvent],
        date_range: Tuple[date, date],
        family_prefs=None,
    ) -> List[EventAssociation]:
        """使用LLM和规则引擎发现关联（双重保障）。"""
        if not curated_events:
            return []

        all_associations = []

        for event in curated_events:
            if event.id is None:
                logger.warning(
                    "Skip association discovery for event without persisted id: title=%r",
                    event.title,
                )
                continue

            trip_context: Optional[str] = None
            if event.event_type in ("business_trip", "travel") and event.trip_id:
                trip_context = self._build_trip_context_for_llm(
                    event, curated_events
                )

            # 1. 规则引擎发现（快速、可靠）
            rule_associations = await self.rule_engine.discover_associations(
                family_id, event
            )

            # 2. LLM发现（智能、灵活）
            llm_associations = await self._llm_discover_associations(
                family_id, event, date_range, trip_context=trip_context
            )

            # 3. 合并去重（精确匹配）
            merged = self._merge_associations(rule_associations, llm_associations)

            # 4. 过滤低质量关联
            filtered = self._filter_low_quality_associations(merged)

            # 5. Apply learned preference rules (E2 Layer 3)
            if event.user_id:
                filtered = await self._apply_preference_rules(
                    filtered, event.user_id, event,
                )

            all_associations.extend(filtered)

        # 6. LLM整合：像秘书一样审阅全部关联，合并语义重复项
        if len(all_associations) > 1:
            all_associations = await self._consolidate_associations(all_associations)

        return all_associations

    @staticmethod
    def _build_trip_context_for_llm(
        trip_event: CuratedEvent,
        all_events: List[CuratedEvent],
    ) -> str:
        """Build a human-readable trip overview for the LLM."""
        child_events = [
            e for e in all_events
            if e.trip_id == trip_event.trip_id and e is not trip_event
        ]
        child_events.sort(
            key=lambda e: e.normalized_start or datetime.min.replace(tzinfo=timezone.utc)
        )

        location_display = trip_event.location or "\u672a\u77e5"
        lines = [
            f"\u884c\u7a0b\u540d\u79f0: {trip_event.title}",
            f"\u76ee\u7684\u5730: {location_display}",
        ]
        if trip_event.normalized_start and trip_event.normalized_end:
            user_tz = get_user_timezone()
            start_local = trip_event.normalized_start.astimezone(user_tz)
            end_local = trip_event.normalized_end.astimezone(user_tz)
            num_days = (end_local.date() - start_local.date()).days + 1
            lines.append(
                f"\u65e5\u671f: {start_local.strftime('%Y-%m-%d')} ~ "
                f"{end_local.strftime('%Y-%m-%d')} ({num_days}\u5929)"
            )

        if child_events:
            lines.append("\n\u65e5\u7a0b\u5b89\u6392:")
            for ce in child_events:
                time_str = ""
                if ce.normalized_start:
                    ce_local = ce.normalized_start.astimezone(
                        get_user_timezone()
                    )
                    time_str = ce_local.strftime("%m-%d %H:%M")
                loc_str = f" @ {ce.location}" if ce.location else ""
                lines.append(f"  - [{time_str}] {ce.title}{loc_str}")
        else:
            lines.append("\n(\u6682\u65e0\u5177\u4f53\u65e5\u7a0b\u5b89\u6392)")

        return "\n".join(lines)

    async def _llm_discover_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
        date_range: Tuple[date, date],
        *,
        trip_context: Optional[str] = None,
    ) -> List[EventAssociation]:
        """使用LLM发现单个事件的关联。"""
        members = await self._get_members_with_locations(
            family_id,
            event.user_id,
        )
        memories = await self._get_relevant_memories(family_id, [event])
        important_dates = await self._get_important_dates_in_range(family_id, date_range)

        event_data = self._sanitize_for_llm({
            "id": str(event.id) if event.id else "new",
            "title": event.title,
            "event_type": event.event_type,
            "start_time": event.normalized_start.isoformat() if event.normalized_start else None,
            "end_time": event.normalized_end.isoformat() if event.normalized_end else None,
            "location": event.location,
        })
        event_json = json.dumps([event_data], ensure_ascii=False, indent=2)

        members_json = json.dumps(self._sanitize_for_llm(members), ensure_ascii=False, indent=2)
        memories_json = json.dumps(self._sanitize_for_llm(memories), ensure_ascii=False, indent=2)
        dates_json = json.dumps(self._sanitize_for_llm(important_dates), ensure_ascii=False, indent=2)

        if trip_context:
            user_prompt = f"""\u8bf7\u5206\u6790\u4ee5\u4e0b\u591a\u5929\u884c\u7a0b\uff0c\u53d1\u73b0\u6574\u4e2a\u884c\u7a0b\u4e2d\u4e0e\u4eba\u7269\u3001\u8bb0\u5fc6\u7684\u5173\u8054\uff1a

## \u884c\u7a0b\u603b\u89c8
{self._sanitize_for_llm(trip_context)}

## \u4e8b\u4ef6\u4fe1\u606f
{event_json}

## \u5bb6\u5ead\u6210\u5458/\u8054\u7cfb\u4eba\uff08\u542b\u4f4d\u7f6e\uff09
{members_json}

## \u76f8\u5173\u8bb0\u5fc6
{memories_json}

## \u91cd\u8981\u65e5\u671f
{dates_json}

\u8bf7\u4ece\u6574\u4e2a\u884c\u7a0b\u7684\u89c6\u89d2\u53d1\u73b0\u5173\u8054\uff08\u5982\u884c\u7a0b\u671f\u95f4\u53ef\u4ee5\u987a\u4fbf\u89c1\u7684\u4eba\u3001\u884c\u7a0b\u76ee\u7684\u5730\u9644\u8fd1\u7684\u5f85\u529e\u4e8b\u9879\u7b49\uff09\uff0c\u8f93\u51faJSON\u683c\u5f0f\u7684\u5173\u8054\u53d1\u73b0\u7ed3\u679c\u3002"""
        else:
            user_prompt = f"""\u8bf7\u5206\u6790\u4ee5\u4e0b\u4e8b\u4ef6\uff0c\u53d1\u73b0\u4e0e\u4eba\u7269\u3001\u8bb0\u5fc6\u7684\u5173\u8054\uff1a

## \u4e8b\u4ef6\u5217\u8868
{event_json}

## \u5bb6\u5ead\u6210\u5458/\u8054\u7cfb\u4eba\uff08\u542b\u4f4d\u7f6e\uff09
{members_json}

## \u76f8\u5173\u8bb0\u5fc6
{memories_json}

## \u91cd\u8981\u65e5\u671f
{dates_json}

\u8bf7\u8f93\u51faJSON\u683c\u5f0f\u7684\u5173\u8054\u53d1\u73b0\u7ed3\u679c\u3002"""

        try:
            response = await self.llm.chat(
                messages=[
                    LLMMessage(role="system", content=ENHANCED_ASSOCIATION_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                temperature=DEFAULT_LLM_TEMPERATURE,
                max_tokens=settings.curation_association_max_tokens,
            )

            response_text = self._strip_markdown_json(response.text)
            parsed = json.loads(response_text)
            llm_response = LLMAssociationResponse(**parsed)

            valid_association_types = {e.value for e in AssociationType}
            valid_target_types = {e.value for e in TargetType}
            valid_priorities = {e.value for e in AssociationPriority}

            associations = []
            for llm_assoc in llm_response.associations:
                if llm_assoc.source_event_id != str(event.id):
                    logger.warning(f"LLM returned association for wrong event: {llm_assoc.source_event_id}")
                    continue

                if llm_assoc.association_type not in valid_association_types:
                    logger.warning(
                        f"LLM returned invalid association_type '{llm_assoc.association_type}', skipping"
                    )
                    continue
                if llm_assoc.target_type not in valid_target_types:
                    logger.warning(
                        f"LLM returned invalid target_type '{llm_assoc.target_type}', skipping"
                    )
                    continue
                if llm_assoc.priority not in valid_priorities:
                    logger.warning(
                        f"LLM returned invalid priority '{llm_assoc.priority}', defaulting to 'convenient'"
                    )
                    llm_assoc.priority = AssociationPriority.CONVENIENT.value

                associations.append(EventAssociation(
                    family_id=family_id,
                    source_event_id=event.id,
                    target_id=llm_assoc.target_id,
                    target_type=llm_assoc.target_type,
                    association_type=llm_assoc.association_type,
                    title=llm_assoc.title,
                    reason=llm_assoc.reason,
                    priority=llm_assoc.priority,
                    confidence=llm_assoc.confidence,
                ))

            return associations

        except Exception as e:
            logger.error(f"LLM association discovery failed for event {event.id}: {e}")
            return []

    _PRIORITY_RANK = {
        "strongly_recommend": 0,
        "convenient": 1,
        "optional": 2,
    }

    def _merge_associations(
        self,
        rule_associations: List[EventAssociation],
        llm_associations: List[EventAssociation],
    ) -> List[EventAssociation]:
        """合并规则引擎和LLM发现的关联，去重。"""
        all_associations = list(rule_associations) + list(llm_associations)
        return self._dedup_associations(all_associations)

    def _dedup_associations(
        self,
        associations: List[EventAssociation],
    ) -> List[EventAssociation]:
        """对关联列表去重：同一事件下、同一目标只保留优先级最高的关联。"""
        seen_by_target: Dict[tuple, EventAssociation] = {}
        seen_by_title: Dict[tuple, EventAssociation] = {}
        result = []

        for assoc in associations:
            target_key = (
                str(assoc.source_event_id),
                str(assoc.target_id),
            ) if assoc.target_id else None

            title_text = (assoc.title or "").strip().lower()
            title_key = (
                str(assoc.source_event_id),
                title_text,
            ) if title_text else None

            def is_better(new_assoc, old_assoc):
                new_rank = self._PRIORITY_RANK.get(new_assoc.priority, 99)
                old_rank = self._PRIORITY_RANK.get(old_assoc.priority, 99)
                if new_rank != old_rank:
                    return new_rank < old_rank
                return (new_assoc.confidence or 0) > (old_assoc.confidence or 0)

            if target_key and target_key in seen_by_target:
                existing = seen_by_target[target_key]
                if is_better(assoc, existing):
                    result.remove(existing)
                    seen_by_target[target_key] = assoc
                    result.append(assoc)
                continue

            if title_key is not None and title_key in seen_by_title:
                existing = seen_by_title[title_key]
                if is_better(assoc, existing):
                    result.remove(existing)
                    seen_by_title[title_key] = assoc
                    result.append(assoc)
                continue

            if target_key:
                seen_by_target[target_key] = assoc
            if title_key is not None:
                seen_by_title[title_key] = assoc
            result.append(assoc)

        return result

    def _filter_low_quality_associations(
        self,
        associations: List[EventAssociation],
    ) -> List[EventAssociation]:
        """Filter low quality associations using confidence + information density."""
        if not associations:
            return []

        min_confidence = max(0.0, min(float(settings.curation_association_min_confidence), 1.0))
        top_k = max(1, int(settings.curation_association_top_k))
        low_info_limit = max(0, int(settings.curation_low_information_association_limit))

        candidates = [
            assoc for assoc in associations
            if (assoc.confidence or 0.0) >= min_confidence
        ]
        if not candidates:
            return []

        def sort_key(assoc: EventAssociation) -> tuple:
            return (
                self._PRIORITY_RANK.get(assoc.priority, 99),
                -(assoc.confidence or 0.0),
                -len((assoc.reason or "").strip()),
            )

        sorted_candidates = sorted(candidates, key=sort_key)
        filtered: List[EventAssociation] = []
        low_info_count = 0
        for assoc in sorted_candidates:
            if self._is_low_information_association(assoc):
                if low_info_count >= low_info_limit:
                    continue
                low_info_count += 1
            filtered.append(assoc)
            if len(filtered) >= top_k:
                break

        return filtered

    @staticmethod
    def _is_low_information_association(assoc: EventAssociation) -> bool:
        """Detect low-information associations without keyword hardcoding.

        Associations with enrichments but no title/reason are structural
        (from rule engine, awaiting LLM text) and exempt from this check.
        """
        if getattr(assoc, "enrichments", None) and not (assoc.title or "").strip():
            return False
        title = (assoc.title or "").strip()
        reason = (assoc.reason or "").strip()
        if len(title) < int(settings.curation_association_min_title_chars):
            return True
        if len(reason) < int(settings.curation_association_min_reason_chars):
            return True
        return False

    @staticmethod
    def _rule_matches_context(
        rule,
        event_type: str,
        association_type: str,
        target_id: Optional[str] = None,
        event_location: Optional[str] = None,
    ) -> bool:
        """Check if a preference rule matches the given context."""
        if rule.condition_event_type and event_type != rule.condition_event_type:
            return False
        if rule.condition_suggestion_type and association_type != rule.condition_suggestion_type:
            return False
        if rule.condition_person_id and target_id != str(rule.condition_person_id):
            return False
        if rule.condition_location and (not event_location or rule.condition_location not in event_location):
            return False
        return True

    async def _apply_preference_rules(
        self,
        associations: List[EventAssociation],
        user_id: UUID,
        event: CuratedEvent,
    ) -> List[EventAssociation]:
        """Apply learned preference rules to adjust association confidence (E2 Layer 3).

        Active, non-expired UserPreferenceRule rows are matched against each
        association.  Matching ``suppress`` rules scale confidence down by
        ``(1 - rule.confidence)``; ``deprioritize`` rules apply a softer
        factor of ``(1 - rule.confidence * 0.5)``.

        Returns the (potentially confidence-adjusted) list -- no items are
        removed outright so the downstream top-K filter can still select them.

        To avoid unintended DB writes, adjusted associations are shallow-copied
        and detached from the session before mutation.
        """
        try:
            stmt = (
                select(UserPreferenceRule)
                .where(
                    and_(
                        UserPreferenceRule.user_id == user_id,
                        UserPreferenceRule.is_active.is_(True),
                        UserPreferenceRule.expires_at > utc_now(),
                    )
                )
            )
            result = await self.session.execute(stmt)
            rules = result.scalars().all()
        except Exception as exc:
            logger.warning("Failed to load preference rules for user %s: %s", user_id, exc)
            return associations

        if not rules:
            return associations

        event_type = getattr(event, "event_type", "") or ""
        event_location = getattr(event, "location", None) or ""

        adjusted: List[EventAssociation] = []
        for assoc in associations:
            adjustment = 1.0
            matched_rules: List = []
            for rule in rules:
                if not self._rule_matches_context(
                    rule,
                    event_type=event_type,
                    association_type=assoc.association_type or "",
                    target_id=assoc.target_id,
                    event_location=event_location,
                ):
                    continue

                matched_rules.append(rule)
                if rule.action == "suppress":
                    adjustment *= (1.0 - rule.confidence)
                elif rule.action == "deprioritize":
                    adjustment *= (1.0 - rule.confidence * 0.5)

            if adjustment < 1.0:
                # Create a detached copy to avoid mutating session-attached objects
                adjusted_assoc = copy(assoc)
                make_transient(adjusted_assoc)
                adjusted_assoc.confidence = max(0.05, (assoc.confidence or 0.8) * adjustment)
                adjusted.append(adjusted_assoc)

                # Audit trail: record suppression signals for each matching rule
                for rule in matched_rules:
                    await self._record_suppression_signal(
                        user_id, event, rule, assoc,
                    )
            else:
                adjusted.append(assoc)

        return adjusted

    async def _record_suppression_signal(
        self,
        user_id: UUID,
        event: CuratedEvent,
        rule,
        association: EventAssociation,
    ) -> None:
        """Record a PreferenceSignal audit entry when a rule suppresses an association."""
        try:
            from ..models import PreferenceSignal

            signal = PreferenceSignal(
                user_id=user_id,
                family_id=event.family_id,
                signal_type="suppression_applied",
                source_type="association",
                source_id=association.id or event.id,
                source_context={
                    "rule_id": str(rule.id) if rule.id else None,
                    "rule_action": rule.action,
                    "rule_confidence": rule.confidence,
                    "association_type": association.association_type,
                    "association_title": association.title,
                    "event_type": event.event_type,
                },
                category_key=f"suppression:{rule.action}:{event.event_type or 'unknown'}",
                processed=True,  # Audit-only, not for extraction
            )
            self.session.add(signal)
        except Exception as exc:
            logger.warning(
                "Failed to record suppression audit signal: %s", exc,
            )

    async def _consolidate_associations(
        self,
        associations: List[EventAssociation],
    ) -> List[EventAssociation]:
        """使用LLM审阅关联列表，合并语义重复项。

        像一个秘书在整理备忘录时，把"了解深圳春节活动"、
        "春节期间深圳活动信息可顺路了解"、"了解2026年春节深圳特别活动"
        合并成一条简洁的提醒。
        """
        from .prompts import ASSOCIATION_CONSOLIDATION_PROMPT

        items_for_llm = []
        for i, assoc in enumerate(associations):
            items_for_llm.append({
                "index": i,
                "title": assoc.title,
                "reason": assoc.reason,
                "priority": assoc.priority,
                "target_type": assoc.target_type,
                "confidence": assoc.confidence,
            })

        user_prompt = (
            f"以下是为行程发现的 {len(associations)} 条关联建议，"
            f"请审阅并整合：\n\n"
            + json.dumps(items_for_llm, ensure_ascii=False, indent=2)
        )

        try:
            response = await self.llm.chat(
                messages=[
                    LLMMessage(role="system", content=ASSOCIATION_CONSOLIDATION_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                temperature=0.2,
                max_tokens=1500,
            )

            raw = self._strip_markdown_json(response.text)
            result = json.loads(raw)

            keep_indices = set()
            rewrites = {}

            for group in result.get("groups", []):
                keep_idx = group.get("keep_index")
                if keep_idx is not None and 0 <= keep_idx < len(associations):
                    keep_indices.add(keep_idx)
                    new_title = group.get("merged_title")
                    new_reason = group.get("merged_reason")
                    if new_title:
                        rewrites[keep_idx] = (new_title, new_reason)

            for idx in result.get("standalone_indices", []):
                if isinstance(idx, int) and 0 <= idx < len(associations):
                    keep_indices.add(idx)

            if not keep_indices:
                logger.warning("LLM consolidation returned no keep indices, skipping")
                return associations

            consolidated = []
            for idx in sorted(keep_indices):
                assoc = associations[idx]
                if idx in rewrites:
                    new_title, new_reason = rewrites[idx]
                    if new_title and not looks_internal_language(new_title):
                        assoc.title = new_title
                    if new_reason and not looks_internal_language(new_reason):
                        assoc.reason = new_reason
                consolidated.append(assoc)

            logger.info(
                "Association consolidation: %d → %d",
                len(associations),
                len(consolidated),
            )
            return consolidated

        except Exception as e:
            logger.warning("Association consolidation skipped: %s", e)
            return associations

    # ------------------------------------------------------------------
    # E2: Reverse signal confidence decay
    # ------------------------------------------------------------------

    async def on_association_confirmed(
        self,
        user_id: UUID,
        event: CuratedEvent,
        association: EventAssociation,
    ) -> None:
        """Handle user confirmation of an association that may have been suppressed.

        If the confirmed association was being suppressed by active preference
        rules, those rules have their confidence decayed so the system adapts.
        """
        try:
            await self._decay_overridden_rules(user_id, event, association)
        except Exception as exc:
            logger.warning(
                "Preference rule decay failed for user %s association %s: %s",
                user_id, association.id, exc,
            )

    async def _decay_overridden_rules(
        self,
        user_id: UUID,
        event: CuratedEvent,
        association: EventAssociation,
    ) -> None:
        """Decay confidence of preference rules that match a confirmed association.

        When a user actively confirms an association that was being suppressed,
        the matching rule's confidence is multiplied by 0.8 (20% decay).
        If confidence drops below 0.3, the rule is deactivated.
        """
        event_type = getattr(event, "event_type", "") or ""
        event_location = getattr(event, "location", None) or ""

        stmt = (
            select(UserPreferenceRule)
            .where(
                and_(
                    UserPreferenceRule.user_id == user_id,
                    UserPreferenceRule.is_active.is_(True),
                    UserPreferenceRule.expires_at > utc_now(),
                )
            )
        )
        result = await self.session.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            if not self._rule_matches_context(
                rule,
                event_type=event_type,
                association_type=association.association_type or "",
                target_id=association.target_id,
                event_location=event_location,
            ):
                continue

            new_confidence = rule.confidence * 0.8
            if new_confidence < 0.3:
                rule.is_active = False
                logger.info(
                    "Deactivated preference rule %s (confidence %.2f -> %.2f < 0.3) "
                    "after user confirmed suppressed association",
                    rule.id, rule.confidence, new_confidence,
                )
            else:
                logger.info(
                    "Decayed preference rule %s confidence %.2f -> %.2f "
                    "after user confirmed suppressed association",
                    rule.id, rule.confidence, new_confidence,
                )
            rule.confidence = new_confidence

    # ------------------------------------------------------------------
    # Phase 2: Association-driven PendingAction generation
    # ------------------------------------------------------------------

    async def _get_target_temperature(
        self,
        user_id: Optional[UUID],
        member_id_str: str,
    ) -> Optional[str]:
        """Lazily fetch temperature status for a person target."""
        if user_id is None:
            return None
        try:
            target_uuid = UUID(member_id_str)
        except ValueError:
            logger.debug("Temperature lookup: invalid UUID %s", member_id_str)
            return None
        try:
            from ...relationship.thermometer import compute_temperature
            temp = await compute_temperature(user_id, target_uuid, self.session)
            return temp.status
        except Exception:
            logger.warning(
                "Temperature lookup failed for %s", member_id_str, exc_info=True
            )
            return None

    async def _get_days_since_contact(
        self,
        family_id: UUID,
        member_id_str: str,
    ) -> Optional[int]:
        """Return days since last contact for a member, or None if unknown."""
        try:
            target_uuid = UUID(member_id_str)
        except ValueError:
            logger.debug(
                "days_since_contact: invalid UUID %s", member_id_str
            )
            return None
        try:
            from ...member.models import PersonProfile, ProfileStatus
            stmt = (
                select(PersonProfile.last_mentioned_at)
                .where(
                    PersonProfile.member_id == target_uuid,
                    PersonProfile.family_id == family_id,
                    PersonProfile.status == ProfileStatus.ACTIVE.value,
                )
                .limit(1)
            )
            last_mentioned = await self.session.scalar(stmt)
            if last_mentioned is None:
                return None
            return max(0, (utc_now() - last_mentioned).days)
        except Exception:
            logger.warning(
                "days_since_contact lookup failed for %s",
                member_id_str,
                exc_info=True,
            )
            return None

    async def _should_generate_pending_action(
        self,
        association: EventAssociation,
        event: CuratedEvent,
    ) -> Optional[str]:
        """Determine if an association should be escalated to a PendingAction.

        Returns an action_type string ("suggest_meeting", "suggest_greeting",
        "suggest_gift") when conditions are met, or None otherwise.
        """
        assoc_type = association.association_type or ""
        target_type = association.target_type or ""
        confidence = association.confidence or 0.0

        # --- suggest_meeting: location-based, high confidence, cold/cool relation ---
        if assoc_type == "location" and target_type == "person":
            # Never suggest meeting yourself
            if association.target_id and str(association.target_id) == str(event.user_id):
                return None
            if confidence >= _SUGGEST_MEETING_CONFIDENCE_THRESHOLD:
                temp = await self._get_target_temperature(
                    event.user_id, association.target_id,
                )
                if temp in _SUGGEST_MEETING_ALLOWED_TEMPS:
                    return "suggest_meeting"

        # --- suggest_greeting: stale contact (stale_contact assoc with 60+ day gap) ---
        if assoc_type == "stale_contact" and target_type == "person":
            if event.normalized_start:
                days_until = (event.normalized_start.date() - utc_now().date()).days
                if days_until <= _SUGGEST_GREETING_DEPARTURE_DAYS:
                    days_since = await self._get_days_since_contact(
                        association.family_id, association.target_id,
                    )
                    if days_since is not None and days_since >= _SUGGEST_GREETING_DAYS_THRESHOLD:
                        return "suggest_greeting"

        # --- suggest_gift: temporal + date target (birthday / anniversary) ---
        if assoc_type == "temporal" and target_type == "date":
            reason_lower = (association.reason or "").lower()
            title_lower = (association.title or "").lower()
            gift_keywords = (
                "生日", "纪念日", "birthday", "anniversary",
                "母亲节", "父亲节", "情人节", "结婚", "周年",
                "mother's day", "father's day", "valentine",
                "wedding", "graduation", "毕业",
            )
            if any(kw in reason_lower or kw in title_lower for kw in gift_keywords):
                return "suggest_gift"

        return None

    async def _generate_action_draft(
        self,
        action_type: str,
        association: EventAssociation,
        event: CuratedEvent,
        member_name: str,
    ) -> str:
        """Generate a natural draft message for the suggested action via Haiku.

        Falls back to a template string when the LLM call fails.
        """
        action_type_cn_map = {
            "suggest_meeting": "顺路会面邀约",
            "suggest_greeting": "久未联系问候",
            "suggest_gift": "重要日期祝福",
        }
        action_type_cn = action_type_cn_map.get(action_type, "联系")

        destination = event.location or event.city or "目的地"
        user_tz = get_user_timezone()
        start_date = (
            event.normalized_start.astimezone(user_tz).strftime("%m月%d日")
            if event.normalized_start else "近期"
        )
        end_date = (
            event.normalized_end.astimezone(user_tz).strftime("%m月%d日")
            if event.normalized_end else ""
        )
        date_range_str = f"{start_date}~{end_date}" if end_date else start_date

        # Per-action-type prompt customization
        if action_type == "suggest_gift":
            prompt = (
                f"你是一位助理，帮用户起草一条简短自然的祝福/送礼消息。\n"
                f"场景: {action_type_cn}\n"
                f"联系人: {member_name}\n"
                f"关联原因: {association.reason}\n\n"
                f"要求：\n"
                f"- 语气温暖真诚，像真人发的消息，不要AI腔\n"
                f"- 简洁，不超过80字\n"
                f"- 包含具体的祝福或礼物提议\n"
                f"- 自然收尾，不必以问句结尾\n\n"
                f"直接输出消息文本，不要解释。"
            )
        else:
            prompt = (
                f"你是一位助理，帮用户起草一条简短自然的联系消息。\n"
                f"场景: {action_type_cn}\n"
                f"正在前往: {destination}（{date_range_str}）\n"
                f"联系人: {member_name}\n"
                f"关联原因: {association.reason}\n\n"
                f"要求：\n"
                f"- 语气自然，像真人发的消息，不要AI腔\n"
                f"- 简洁，不超过80字\n"
                f"- 包含出行日期和目的地信息\n"
                f"- 以问句结尾（留出对方拒绝的余地）\n\n"
                f"直接输出消息文本，不要解释。"
            )

        try:
            client = get_haiku_client()
            response = await client.messages.create(
                model=settings.fast_worker_model,
                max_tokens=_HAIKU_DRAFT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if text_parts:
                return text_parts[0].strip()
        except Exception as exc:
            logger.warning("Haiku draft generation failed for %s: %s", action_type, exc)

        # Fallback templates
        templates = {
            "suggest_meeting": f"{member_name}，我{start_date}到{destination}，方便见面叙叙吗？",
            "suggest_greeting": f"{member_name}，好久不见！我{start_date}会在{destination}，有空聊聊吗？",
            "suggest_gift": f"{member_name}，{association.reason}，想提前送上祝福，方便吗？",
        }
        return templates.get(action_type, f"联系{member_name}：{association.reason}")

    async def _create_pending_action_from_association(
        self,
        association: EventAssociation,
        event: CuratedEvent,
        action_type: str,
        draft_content: str,
        user_id: UUID,
        family_id: UUID,
        member_name: str = "",
    ) -> bool:
        """Create a PendingAction from an association, with flood-control.

        Returns True if created, False if skipped due to rate limits.
        """
        from ....modules.conversation.pending_action import (
            ActionStatus,
            ActionType,
            PendingAction,
        )

        # Guard: max _SUGGEST_ACTION_MAX_PENDING unhandled suggest_* per user
        count_stmt = select(func.count(PendingAction.id)).where(
            PendingAction.user_id == user_id,
            PendingAction.action_type.like("suggest_%"),
            PendingAction.status == ActionStatus.PENDING.value,
        )
        pending_count = await self.session.scalar(count_stmt)
        if (pending_count or 0) >= _SUGGEST_ACTION_MAX_PENDING:
            logger.debug(
                "Skipping PendingAction for user %s: %d suggest_* already pending",
                user_id, pending_count,
            )
            return False

        # Guard: cooldown — same (user_id, target member, action_type) within N days
        target_id = association.target_id
        cooldown_cutoff = utc_now() - timedelta(days=_SUGGEST_ACTION_COOLDOWN_DAYS)
        recent_stmt = (
            select(PendingAction.id)
            .where(
                PendingAction.user_id == user_id,
                PendingAction.action_type == action_type,
                PendingAction.payload["target_id"].astext == target_id,
                PendingAction.created_at >= cooldown_cutoff,
            )
            .limit(1)
        )
        recent = await self.session.scalar(recent_stmt)
        if recent is not None:
            logger.debug(
                "Skipping PendingAction for target %s: within cooldown window",
                target_id,
            )
            return False

        # Guard: reject suppress — user rejected same (target, action_type) within 30 days
        suppress_cutoff = utc_now() - timedelta(days=_SUGGEST_REJECT_SUPPRESS_DAYS)
        rejected_stmt = (
            select(PendingAction.id)
            .where(
                PendingAction.user_id == user_id,
                PendingAction.action_type == action_type,
                PendingAction.payload["target_id"].astext == target_id,
                PendingAction.status == ActionStatus.REJECTED.value,
                PendingAction.created_at >= suppress_cutoff,
            )
            .limit(1)
        )
        rejected = await self.session.scalar(rejected_stmt)
        if rejected is not None:
            logger.debug(
                "Skipping PendingAction for target %s: rejected within suppress window",
                target_id,
            )
            return False

        expires_at = utc_now() + timedelta(days=_SUGGEST_ACTION_COOLDOWN_DAYS)

        # Build human-readable date range
        user_tz = get_user_timezone(user_id)
        start_str = event.normalized_start.astimezone(user_tz).strftime(
            "%m月%d日"
        ) if event.normalized_start else ""
        end_str = event.normalized_end.astimezone(user_tz).strftime(
            "%m月%d日"
        ) if event.normalized_end else ""
        date_range = f"{start_str}~{end_str}" if end_str else start_str

        location = event.location or event.city or ""
        trip_label = event.trip_name or event.title

        display_ctx = {
            "member_name": member_name if member_name != association.target_id else "",
            "trip_label": trip_label,
            "date_range": date_range,
            "location": location,
            "draft_content": draft_content,
            "occasion": association.title,
            "reason": association.reason,
        }

        action = PendingAction(
            user_id=user_id,
            family_id=family_id,
            action_type=action_type,
            association_id=association.id,
            draft_content=draft_content,
            status=ActionStatus.PENDING.value,
            expires_at=expires_at,
            payload={
                "source_event_id": str(event.id),
                "target_id": association.target_id,
                "target_type": association.target_type,
                "association_type": association.association_type,
                "association_title": association.title,
            },
            display_data=build_display_data(
                action_type,
                display_ctx,
                description=association.reason,
            ),
        )
        self.session.add(action)
        logger.info(
            "Created PendingAction type=%s for user=%s association=%s",
            action_type, user_id, association.id,
        )
        return True

    async def _generate_pending_actions_for_associations(
        self,
        saved_associations: List[EventAssociation],
        event: CuratedEvent,
        user_id: UUID,
        family_id: UUID,
    ) -> int:
        """For each saved association, check and create a PendingAction if warranted.

        Returns the count of actions created.
        """
        from sqlalchemy import select as sa_select
        from ....modules.member.models.member import Member

        created_count = 0
        for assoc in saved_associations:
            if assoc.source_event_id != event.id:
                continue

            action_type = await self._should_generate_pending_action(assoc, event)
            if not action_type:
                continue

            # Resolve member name for draft generation
            member_name = assoc.target_id  # fallback: use raw ID
            if assoc.target_type == "person":
                try:
                    target_uuid = UUID(assoc.target_id)
                    member_stmt = sa_select(Member.name).where(Member.id == target_uuid)
                    member_name = await self.session.scalar(member_stmt) or assoc.target_id
                except (ValueError, Exception) as exc:
                    logger.debug("Could not resolve member name for %s: %s", assoc.target_id, exc)

            draft = await self._generate_action_draft(action_type, assoc, event, member_name)
            created = await self._create_pending_action_from_association(
                assoc, event, action_type, draft, user_id, family_id,
                member_name=member_name,
            )
            if created:
                created_count += 1

        return created_count
