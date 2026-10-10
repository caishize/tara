"""Step 3 filters for ContextAssembler: Privacy, Exclusion, and Inference Guard.

Implements three chained filters for the context assembly pipeline:
  1. PrivacyFilter  -- sensitivity_level-based access control
  2. ExclusionFilter -- entity ID-based exclusion with L2 override
  3. PrivacyInferenceGuard -- removes inferable fields to prevent indirect leaks
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from .context_assembler import ContextItem

# Default cooldown period (days) for re-suggesting dismissed items.
DEFAULT_COOLDOWN_DAYS = 7.0

# Feedback weight threshold below which a memory is considered excluded.
FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD = 0.3

# Fields that can leak location if passed to LLM.
LOCATION_INFERABLE_FIELDS = frozenset({"location", "coordinates", "address"})
# Fields that can leak schedule if passed to LLM.
SCHEDULE_INFERABLE_FIELDS = frozenset({"schedule_gaps", "free_slots"})


class PrivacyFilter:
    """Filter items based on sensitivity_level and viewer context.

    Sensitivity levels:
    - PUBLIC:    always passes
    - FAMILY:    passes if viewer is in the same family
    - PRIVATE:   passes only if viewer is the item creator
    - SENSITIVE: NEVER passes (never enters LLM context)
    """

    @staticmethod
    def apply(
        items: List[ContextItem],
        viewer_user_id: str,
        viewer_family_id: str,
    ) -> Tuple[List[ContextItem], int]:
        """Filter items by privacy level.

        Returns (kept_items, filtered_count).
        """
        kept: List[ContextItem] = []
        filtered = 0
        for item in items:
            level = item.sensitivity_level
            if level == "sensitive":
                filtered += 1
                continue
            if level == "private":
                if item.source_member_id is None or item.source_member_id != viewer_user_id:
                    filtered += 1
                    continue
            if level == "family":
                item_family = item.metadata.get("family_id")
                if item_family is not None and str(item_family) != viewer_family_id:
                    filtered += 1
                    continue
            kept.append(item)
        return kept, filtered


class ExclusionFilter:
    """Filter items based on entity-level exclusion rules.

    Uses entity_ids on ContextItem (UUIDs) for matching, NOT string matching.
    Supports L2 Override: if the user mentions a dismissed entity in the
    current message (entity present in resolved_entity_ids), the exclusion
    is overridden.

    Exclusion sources:
    - feedback_weight < FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD
    - metadata["dismissed_entity_ids"] (set by fetchers from insight_feedbacks
      and association dismiss records)
    - metadata["last_dismissed_at"] with cooldown period check
    """

    @staticmethod
    def apply(
        items: List[ContextItem],
        resolved_entity_ids: Set[UUID],
        dismissed_entity_ids: Optional[Set[str]] = None,
        cooldown_days: float = DEFAULT_COOLDOWN_DAYS,
    ) -> Tuple[List[ContextItem], int]:
        """Filter items by exclusion rules with L2 override.

        Args:
            items: Items to filter.
            resolved_entity_ids: Entity UUIDs from Step 0 entity linking.
                If the user's current message mentions a dismissed entity,
                the exclusion is overridden.
            dismissed_entity_ids: Pre-fetched set of entity ID strings that
                have been dismissed via insight_feedbacks or association feedback.
            cooldown_days: Days before a dismissed suggestion can reappear.

        Returns (kept_items, filtered_count).
        """
        resolved_id_strs: Set[str] = {str(uid) for uid in resolved_entity_ids}
        excluded_ids: Set[str] = dismissed_entity_ids or set()

        kept: List[ContextItem] = []
        filtered = 0
        for item in items:
            if ExclusionFilter._should_exclude(
                item, resolved_id_strs, excluded_ids, cooldown_days,
            ):
                filtered += 1
            else:
                kept.append(item)
        return kept, filtered

    @staticmethod
    def _should_exclude(
        item: ContextItem,
        resolved_id_strs: Set[str],
        excluded_ids: Set[str],
        cooldown_days: float,
    ) -> bool:
        """Determine if a single item should be excluded.

        Returns True if the item should be filtered out.
        """
        # 1. Low feedback_weight indicates repeatedly negative feedback
        if item.feedback_weight < FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD:
            # L2 Override: user explicitly mentioned this entity
            if _has_l2_override(item.entity_ids, resolved_id_strs):
                return False
            return True

        # 2. Check if any entity_id is in the dismissed set
        if excluded_ids and item.entity_ids:
            matched_dismissed = set(item.entity_ids) & excluded_ids
            if matched_dismissed:
                # L2 Override
                if _has_l2_override(item.entity_ids, resolved_id_strs):
                    return False
                return True

        # 3. Cooldown check on per-item dismissed_entity_ids in metadata
        item_dismissed = item.metadata.get("dismissed_entity_ids")
        if item_dismissed and item.entity_ids:
            meta_dismissed = set(item_dismissed) if isinstance(item_dismissed, (list, tuple, set)) else set()
            if set(item.entity_ids) & meta_dismissed:
                if _has_l2_override(item.entity_ids, resolved_id_strs):
                    return False
                return True

        # 4. Cooldown period for repeated suggestions
        last_dismissed = item.metadata.get("last_dismissed_at")
        if isinstance(last_dismissed, datetime):
            from ..core.utils.timezone import utc_now
            days_since = (utc_now() - last_dismissed).total_seconds() / 86400.0
            if days_since < cooldown_days:
                if _has_l2_override(item.entity_ids, resolved_id_strs):
                    return False
                return True

        return False


def _has_l2_override(entity_ids: Tuple[str, ...], resolved_id_strs: Set[str]) -> bool:
    """Check if user explicitly mentioned any of the item's entities.

    If the user's current message references a dismissed entity (entity in
    resolved_entity_ids from Step 0), the exclusion is overridden.
    """
    if not entity_ids or not resolved_id_strs:
        return False
    return bool(set(entity_ids) & resolved_id_strs)


class PrivacyInferenceGuard:
    """Prevent LLM from inferring private data through indirect information.

    Problem: Even if a family member's location is hidden, the LLM can infer
    it from suggestions like "meet in the middle". This guard strips inferable
    fields from context items based on per-member privacy settings.

    Privacy settings structure (dict keyed by member_id string):
        {
            "<member_id>": {
                "share_location": True/False,
                "share_schedule": True/False,
            },
        }

    Items without source_member_id pass through unchanged.
    """

    @staticmethod
    def sanitize(
        items: List[ContextItem],
        privacy_settings: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[ContextItem]:
        """Remove inferable fields from items based on privacy settings.

        Returns a new list. Items are immutable so new copies are created
        only when fields need to be removed.
        """
        if not privacy_settings:
            return items

        result: List[ContextItem] = []
        for item in items:
            result.append(_sanitize_item(item, privacy_settings))
        return result


def _sanitize_item(
    item: ContextItem,
    privacy_settings: Dict[str, Dict[str, Any]],
) -> ContextItem:
    """Sanitize a single item based on its source_member_id's privacy settings."""
    if not item.source_member_id:
        return item

    member_privacy = privacy_settings.get(item.source_member_id)
    if not member_privacy:
        return item

    fields_to_remove: List[str] = []
    if not member_privacy.get("share_location", True):
        fields_to_remove.extend(
            f for f in LOCATION_INFERABLE_FIELDS if f in item.metadata
        )
    if not member_privacy.get("share_schedule", True):
        fields_to_remove.extend(
            f for f in SCHEDULE_INFERABLE_FIELDS if f in item.metadata
        )

    if not fields_to_remove:
        return item
    return item.remove_fields(fields_to_remove)


def apply_filters(
    items: List[ContextItem],
    viewer_user_id: str,
    viewer_family_id: str,
    resolved_entity_ids: Set[UUID],
    dismissed_entity_ids: Optional[Set[str]] = None,
    cooldown_days: float = DEFAULT_COOLDOWN_DAYS,
    privacy_settings: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[List[ContextItem], int]:
    """Chain PrivacyFilter -> ExclusionFilter -> PrivacyInferenceGuard.

    Returns (kept_items, total_filtered_count).
    """
    after_privacy, privacy_filtered = PrivacyFilter.apply(
        items, viewer_user_id, viewer_family_id,
    )
    after_exclusion, exclusion_filtered = ExclusionFilter.apply(
        after_privacy, resolved_entity_ids, dismissed_entity_ids, cooldown_days,
    )
    sanitized = PrivacyInferenceGuard.sanitize(after_exclusion, privacy_settings)
    return sanitized, privacy_filtered + exclusion_filtered
