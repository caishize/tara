"""InsightDeliveryLedger -- Redis-based cross-channel delivery tracking.

Prevents the same insight from being delivered via both the morning briefing
and an afternoon sidekick injection on the same day.

Redis key pattern:
    ``insight:delivered:{user_id}:{insight_id}`` → value: channel name
    TTL: 24 hours (auto-expires so next-day delivery is allowed).

No schema migration required -- purely Redis-backed.
"""
from typing import Literal, Optional

from ....config.logging import get_logger
from ....core.cache import redis_client

logger = get_logger(__name__)

_DELIVERY_TTL_SECONDS = 86400  # 24 hours
_DISMISSED_ENTITY_TTL_SECONDS = 48 * 3600  # 48 hours

Channel = Literal["briefing", "sidekick"]


def _delivery_key(user_id: str, insight_id: str) -> str:
    return f"insight:delivered:{user_id}:{insight_id}"


def _dismissed_entity_key(user_id: str, dedup_key: str) -> str:
    return f"insight:dismissed_entity:{user_id}:{dedup_key}"


class InsightDeliveryLedger:
    """Track which insights have already been delivered to a user."""

    async def mark_delivered(
        self,
        user_id: str,
        insight_id: str,
        channel: Channel,
    ) -> None:
        """Record that *insight_id* was delivered via *channel*."""
        rc = redis_client.client
        if rc is None:
            return
        key = _delivery_key(user_id, insight_id)
        try:
            await rc.setex(key, _DELIVERY_TTL_SECONDS, channel)
        except Exception as exc:
            logger.warning(
                "InsightDeliveryLedger: failed to mark delivered "
                "user=%s insight=%s: %s",
                user_id,
                insight_id,
                exc,
            )

    async def was_delivered(
        self,
        user_id: str,
        insight_id: str,
        within_hours: int = 24,
    ) -> bool:
        """Check whether *insight_id* was already delivered within the TTL window.

        The ``within_hours`` parameter is intentionally unused because the
        Redis key already carries a 24 h TTL.  It is kept for interface
        symmetry so callers can express intent.
        """
        rc = redis_client.client
        if rc is None:
            return False
        key = _delivery_key(user_id, insight_id)
        try:
            val = await rc.get(key)
            return val is not None
        except Exception as exc:
            logger.warning(
                "InsightDeliveryLedger: failed to check delivery "
                "user=%s insight=%s: %s",
                user_id,
                insight_id,
                exc,
            )
            return False

    async def get_channel(
        self,
        user_id: str,
        insight_id: str,
    ) -> Optional[str]:
        """Return the channel that delivered the insight, or None."""
        rc = redis_client.client
        if rc is None:
            return None
        key = _delivery_key(user_id, insight_id)
        try:
            return await rc.get(key)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Entity-level dismissed tracking
    # ------------------------------------------------------------------

    async def record_entity_dismissed(
        self,
        user_id: str,
        dedup_key: str,
        is_permanent: bool = False,
    ) -> None:
        """Record that an entity was dismissed.

        Args:
            is_permanent: True for NEVER feedback (no TTL).
        """
        rc = redis_client.client
        if rc is None:
            return
        key = _dismissed_entity_key(user_id, dedup_key)
        try:
            if is_permanent:
                await rc.set(key, "never")
            else:
                await rc.setex(key, _DISMISSED_ENTITY_TTL_SECONDS, "dismissed")
        except Exception as exc:
            logger.warning(
                "InsightDeliveryLedger: entity dismiss failed: %s", exc,
            )

    async def is_entity_dismissed(
        self,
        user_id: str,
        dedup_key: str,
    ) -> bool:
        """Check if entity is in dismissed cooldown."""
        rc = redis_client.client
        if rc is None:
            return False
        key = _dismissed_entity_key(user_id, dedup_key)
        try:
            return await rc.get(key) is not None
        except Exception as exc:
            logger.warning(
                "InsightDeliveryLedger: entity check failed: %s", exc,
            )
            return False
