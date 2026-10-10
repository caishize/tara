"""ShownCountTracker -- Redis-backed shown count persistence.

Tracks how many times recommendations have been shown per family
using Redis keys with a 90-day TTL.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now

logger = get_logger(__name__)

_SHOWN_COUNT_TTL_SECONDS = 90 * 86400  # 90 days, aligned with PreferenceLearner window
_SHOWN_COUNT_KEY_PREFIX = "rec:shown"


def _title_hash(title: str) -> str:
    """Stable hash of a recommendation title for Redis key construction."""
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:12]


class ShownCountTracker:
    """Track how many times recommendations have been shown per family.

    Uses Redis keys: ``rec:shown:{family_id}:{title_hash}``
    Value: JSON ``{"count": N, "last_shown": "ISO timestamp"}``
    TTL: 90 days (aligned with PreferenceLearner decay window).
    """

    def __init__(self, redis_client):
        self._redis = redis_client

    def _key(self, family_id: UUID, title: str) -> str:
        return f"{_SHOWN_COUNT_KEY_PREFIX}:{family_id}:{_title_hash(title)}"

    async def load_counts(
        self,
        family_id: UUID,
        titles: List[str],
    ) -> Dict[str, Tuple[int, Optional[datetime]]]:
        """Load (shown_count, last_shown_at) for a list of recommendation titles.

        Returns a dict keyed by title.
        """
        if not self._redis or not titles:
            return {}

        result: Dict[str, Tuple[int, Optional[datetime]]] = {}
        for title in titles:
            try:
                raw = await self._redis.get(self._key(family_id, title))
                if raw is None:
                    continue
                data = json.loads(raw) if isinstance(raw, str) else raw
                count = int(data.get("count", 0))
                last_shown_str = data.get("last_shown")
                last_shown = (
                    datetime.fromisoformat(last_shown_str)
                    if last_shown_str
                    else None
                )
                result[title] = (count, last_shown)
            except Exception:
                logger.debug(
                    "Failed to load shown count for title=%s", title[:30],
                    exc_info=True,
                )
        return result

    async def increment(
        self,
        family_id: UUID,
        titles: List[str],
    ) -> None:
        """Increment shown_count for each title (fire-and-forget)."""
        if not self._redis or not titles:
            return

        now_iso = utc_now().isoformat()
        for title in titles:
            try:
                key = self._key(family_id, title)
                raw = await self._redis.get(key)
                if raw is not None:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    count = int(data.get("count", 0)) + 1
                else:
                    count = 1
                value = json.dumps(
                    {"count": count, "last_shown": now_iso},
                    ensure_ascii=False,
                )
                await self._redis.set(key, value, ttl=_SHOWN_COUNT_TTL_SECONDS)
            except Exception:
                logger.debug(
                    "Failed to increment shown count for title=%s",
                    title[:30],
                    exc_info=True,
                )
