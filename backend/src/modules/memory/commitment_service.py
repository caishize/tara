"""Commitment Pre-Filter and Social Intent Parser.

Distinguishes genuine commitments from social courtesies in conversations,
preventing over-tracking of vague promises while ensuring actionable
commitments are followed up appropriately.

Chinese social context is important: "改天一起吃饭" is usually courtesy,
while "周三给你报价" is a firm commitment.

Components:
- SocialIntentParser: Classifies statements as genuine, obligation, or courtesy
- CommitmentPreFilter: Gates raw commitments through social intent analysis
- VagueCommitmentTracker: Manages follow-up schedules for tracked commitments
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommitmentType(str, Enum):
    """How firm a commitment is."""
    FIRM = "firm"               # "周三给你报价" — clear promise with specifics
    VAGUE = "vague"             # "改天一起吃饭" — intent without specifics
    CONDITIONAL = "conditional" # "如果方案通过就启动" — depends on condition
    DELEGATED = "delegated"     # "帮我催一下老张" — relay to someone else


class SocialIntentType(str, Enum):
    """The underlying social intent behind a statement."""
    GENUINE = "genuine"
    SOCIAL_COURTESY = "social_courtesy"
    OBLIGATION = "obligation"


class CommitmentStatus(str, Enum):
    """Lifecycle status of a tracked commitment."""
    PENDING = "pending"
    FOLLOWED_UP = "followed_up"
    FULFILLED = "fulfilled"
    EXPIRED = "expired"
    DROPPED = "dropped"


# ---------------------------------------------------------------------------
# Value objects (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SocialIntentResult:
    """Result of social intent classification."""
    type: SocialIntentType
    score: float  # 0.0 = pure courtesy, 1.0 = fully genuine
    reasoning: str = ""


@dataclass(frozen=True)
class CommitmentItem:
    """A commitment extracted from conversation."""
    id: UUID
    commitment_type: CommitmentType
    who_promised: str
    what_promised: str
    to_whom: str
    deadline: Optional[str] = None
    suggested_follow_up: Optional[str] = None
    status: CommitmentStatus = CommitmentStatus.PENDING
    follow_up_count: int = 0
    source_conversation_id: Optional[UUID] = None


# ---------------------------------------------------------------------------
# SocialIntentParser
# ---------------------------------------------------------------------------

# Chinese courtesy markers — strong signals of non-genuine intent
_COURTESY_SIGNALS = re.compile(
    r"(?:改天|有空|下次|回头|以后再说|找机会|等有时间|抽空|"
    r"sometime|one\s+of\s+these\s+days|when\s+i\s+get\s+a\s+chance|"
    r"maybe\s+later|we\s+should\s+sometime)",
    re.IGNORECASE,
)

# Genuine date/action signals — specific temporal or action references
_GENUINE_SIGNALS = re.compile(
    r"(?:周[一二三四五六日天]|星期[一二三四五六日天]|"
    r"明天|后天|今天|今晚|明晚|下午|上午|"
    r"\d{1,2}[月号日]|\d{1,2}:\d{2}|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"tomorrow|tonight|next\s+week|this\s+weekend|"
    r"at\s+\d{1,2}(?::\d{2})?(?:\s*[ap]m)?)",
    re.IGNORECASE,
)

# Obligation markers — require stronger phrasing than bare "should"
_OBLIGATION_SIGNALS = re.compile(
    r"(?:应该|必须|答应了|说好了|承诺|保证|一定|"
    r"have\s+to|must|promised|agreed\s+to|committed\s+to|"
    r"i\s+should|you\s+should|we\s+need\s+to)",
    re.IGNORECASE,
)


async def mark_followed_up(
    commitment_id: UUID,
    db,  # AsyncSession
) -> bool:
    """Mark a commitment as followed up (user completed via insight task).

    Updates CommitmentItemRecord status from 'pending' to 'fulfilled'
    and bumps the updated_at timestamp.

    Returns True if the commitment was found and updated, False otherwise.
    """
    from .commitment_models import CommitmentItemRecord

    result = await db.execute(
        select(CommitmentItemRecord).where(
            CommitmentItemRecord.id == commitment_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        logger.debug(
            "mark_followed_up: commitment %s not found", commitment_id,
        )
        return False

    if record.status in ("fulfilled", "expired", "dropped"):
        logger.debug(
            "mark_followed_up: commitment %s already in terminal status %s",
            commitment_id, record.status,
        )
        return False

    record.status = "fulfilled"
    record.updated_at = utc_now()
    return True


class SocialIntentParser:
    """Classify whether a statement is genuine intent or social courtesy.

    Uses regex-based signal detection for Chinese and English social
    language patterns.  Courtesy signals lower the score, genuine signals
    (specific dates, times) raise it.
    """

    def classify(
        self,
        statement: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SocialIntentResult:
        """Classify a statement's social intent.

        Args:
            statement: The commitment text to classify.
            context: Optional conversation context for additional signals.

        Returns:
            SocialIntentResult with type, score (0.0-1.0), and reasoning.
        """
        if not statement or not statement.strip():
            return SocialIntentResult(
                type=SocialIntentType.SOCIAL_COURTESY,
                score=0.0,
                reasoning="Empty statement",
            )

        courtesy_matches = _COURTESY_SIGNALS.findall(statement)
        genuine_matches = _GENUINE_SIGNALS.findall(statement)
        obligation_matches = _OBLIGATION_SIGNALS.findall(statement)

        # Base score starts at 0.5 (neutral)
        score = 0.5

        # Genuine signals boost score
        score += len(genuine_matches) * 0.15

        # Courtesy signals lower score
        score -= len(courtesy_matches) * 0.2

        # Obligation signals boost moderately
        score += len(obligation_matches) * 0.1

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        # Determine intent type
        reasons: List[str] = []
        if obligation_matches:
            intent_type = SocialIntentType.OBLIGATION
            reasons.append(f"obligation signals: {obligation_matches}")
        elif score >= 0.6:
            intent_type = SocialIntentType.GENUINE
            if genuine_matches:
                reasons.append(f"genuine signals: {genuine_matches}")
        else:
            intent_type = SocialIntentType.SOCIAL_COURTESY
            if courtesy_matches:
                reasons.append(f"courtesy signals: {courtesy_matches}")

        reasoning = "; ".join(reasons) if reasons else "baseline classification"

        return SocialIntentResult(
            type=intent_type,
            score=score,
            reasoning=reasoning,
        )


# ---------------------------------------------------------------------------
# CommitmentPreFilter
# ---------------------------------------------------------------------------


class CommitmentPreFilter:
    """Filter commitments by social intent before tracking.

    Commitments with genuine intent (score >= threshold) are kept.
    Obligations are kept but with extended follow-up windows.
    Social courtesies (score < threshold) are excluded from tracking.
    """

    TRACKING_THRESHOLD = 0.6
    OBLIGATION_FOLLOW_UP_MULTIPLIER = 2

    def __init__(self, parser: Optional[SocialIntentParser] = None):
        self._parser = parser or SocialIntentParser()

    def filter_commitments(
        self,
        raw_commitments: List[CommitmentItem],
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> List[CommitmentItem]:
        """Filter a list of raw commitments by social intent.

        Args:
            raw_commitments: Unfiltered commitment items.
            conversation_context: Optional context for classification.

        Returns:
            Filtered list of commitments worth tracking.
            Social courtesies below TRACKING_THRESHOLD are excluded.
        """
        if not raw_commitments:
            return []

        result: List[CommitmentItem] = []

        for commitment in raw_commitments:
            intent = self._parser.classify(
                commitment.what_promised,
                context=conversation_context,
            )

            if intent.type == SocialIntentType.SOCIAL_COURTESY and intent.score < self.TRACKING_THRESHOLD:
                logger.debug(
                    "Excluding courtesy commitment (score=%.2f): %s",
                    intent.score,
                    commitment.what_promised[:50],
                )
                continue

            if intent.type == SocialIntentType.OBLIGATION:
                extended = self._extend_follow_up(commitment)
                result.append(extended)
                continue

            # GENUINE or high-score courtesy: keep
            result.append(commitment)

        return result

    def _extend_follow_up(self, commitment: CommitmentItem) -> CommitmentItem:
        """Create a new commitment with extended follow-up note for obligations."""
        if commitment.suggested_follow_up is None:
            return commitment

        extended_note = (
            f"{commitment.suggested_follow_up} "
            f"(extended: obligation, {self.OBLIGATION_FOLLOW_UP_MULTIPLIER}x window)"
        )
        return CommitmentItem(
            id=commitment.id,
            commitment_type=commitment.commitment_type,
            who_promised=commitment.who_promised,
            what_promised=commitment.what_promised,
            to_whom=commitment.to_whom,
            deadline=commitment.deadline,
            suggested_follow_up=extended_note,
            status=commitment.status,
            follow_up_count=commitment.follow_up_count,
            source_conversation_id=commitment.source_conversation_id,
        )


# ---------------------------------------------------------------------------
# VagueCommitmentTracker
# ---------------------------------------------------------------------------

# Default follow-up intervals per commitment type (in days)
_DEFAULT_FOLLOW_UP_DAYS: Dict[CommitmentType, int] = {
    CommitmentType.VAGUE: 3,
    CommitmentType.CONDITIONAL: 7,
    CommitmentType.DELEGATED: 2,
    CommitmentType.FIRM: 1,
}

_MAX_FOLLOW_UPS = 3


class VagueCommitmentTracker:
    """Track vague and conditional commitments for follow-up.

    This is a stateless checker — actual commitment storage is external.
    It checks a list of commitment dicts and returns those due for follow-up.
    """

    def __init__(
        self,
        follow_up_days: Optional[Dict[CommitmentType, int]] = None,
        max_follow_ups: int = _MAX_FOLLOW_UPS,
    ):
        self._follow_up_days = follow_up_days or dict(_DEFAULT_FOLLOW_UP_DAYS)
        self._max_follow_ups = max_follow_ups

    def check_and_follow_up(
        self,
        commitments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Find pending commitments that need a follow-up.

        Args:
            commitments: List of commitment dicts with keys:
                commitment_type, status, created_at (ISO string or datetime),
                follow_up_count, last_follow_up_at (optional).

        Returns:
            Subset of commitments that should be followed up now.
        """
        due: List[Dict[str, Any]] = []
        for commitment in commitments:
            if commitment.get("status") != CommitmentStatus.PENDING.value:
                continue
            if self._should_follow_up(commitment):
                due.append(commitment)
        return due

    def _should_follow_up(self, commitment: Dict[str, Any]) -> bool:
        """Determine if a commitment is due for follow-up.

        Criteria:
        1. follow_up_count < max_follow_ups
        2. Days since last follow-up (or creation) >= type threshold
        """
        follow_up_count = commitment.get("follow_up_count", 0)
        if follow_up_count >= self._max_follow_ups:
            return False

        commitment_type_str = commitment.get(
            "commitment_type", CommitmentType.VAGUE.value
        )
        try:
            commitment_type = CommitmentType(commitment_type_str)
        except ValueError:
            commitment_type = CommitmentType.VAGUE

        threshold_days = self._follow_up_days.get(
            commitment_type,
            _DEFAULT_FOLLOW_UP_DAYS[CommitmentType.VAGUE],
        )

        reference_time = (
            commitment.get("last_follow_up_at") or commitment.get("created_at")
        )
        if reference_time is None:
            return True

        if isinstance(reference_time, str):
            try:
                reference_time = datetime.fromisoformat(reference_time)
            except (ValueError, TypeError):
                return True

        now = utc_now()
        days_since = (now - reference_time).total_seconds() / 86400.0
        return days_since >= threshold_days
