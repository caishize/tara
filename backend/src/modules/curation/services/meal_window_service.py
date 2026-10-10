"""
用户作息习惯推断服务

从近90天历史事件的时间分布，推断用户的实际用餐窗口（纯统计，无LLM）。
推断结果保存至 FamilyPreference.inferred_meal_windows。
"""
import logging
from datetime import timedelta
from statistics import median
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now
from ..models import CuratedEvent, FamilyPreference

logger = logging.getLogger(__name__)

# Fallback defaults used when sample is insufficient
_DEFAULT_LUNCH: tuple[int, int, int, int] = (12, 0, 13, 30)
_DEFAULT_DINNER: tuple[int, int, int, int] = (18, 0, 19, 30)

# Minimum events required to attempt inference
_MIN_EVENTS_FOR_INFERENCE = 10

# Historical lookback window in days
_LOOKBACK_DAYS = 90

# Event types excluded from meal-window analysis
_EXCLUDED_EVENT_TYPES = frozenset({"travel", "business_trip"})

# Minimum gap (minutes) between events to count as a free slot
_MIN_GAP_MINUTES = 45

# Minimum number of free-slot samples needed per meal period
_MIN_SLOT_SAMPLES = 5


class MealWindowInferenceService:
    """Infer per-family meal windows from historical event timing."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def infer_and_save(self, family_id: UUID) -> bool:
        """Infer meal windows and persist to FamilyPreference.

        Returns True when windows were updated, False when the sample is
        too small or inference produced no result.
        """
        event_times = await self._collect_event_times(family_id)

        if len(event_times) < _MIN_EVENTS_FOR_INFERENCE:
            logger.debug(
                "family %s: only %d events, skipping meal window inference",
                family_id, len(event_times),
            )
            return False

        windows = self._infer_windows(event_times)
        if windows is None:
            return False

        await self._persist_windows(family_id, windows)
        logger.info("family %s: meal windows updated → %s", family_id, windows)
        return True

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    async def _collect_event_times(
        self, family_id: UUID,
    ) -> list[tuple[str, int, int, int, int]]:
        """Return (date_key, start_h, start_m, end_h, end_m) tuples for recent events.

        The date_key (YYYY-MM-DD) is the local calendar date of the event, used to
        group events from the same day before computing intra-day gaps.
        """
        cutoff = utc_now() - timedelta(days=_LOOKBACK_DAYS)

        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.normalized_start >= cutoff,
                CuratedEvent.normalized_end.isnot(None),
                CuratedEvent.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        events = result.scalars().all()

        times: list[tuple[str, int, int, int, int]] = []
        for ev in events:
            if ev.event_type in _EXCLUDED_EVENT_TYPES:
                continue
            # Use local time directly (DB stores UTC; tolocal handled by ORM TZ)
            start = ev.normalized_start
            end = ev.normalized_end
            if start is None or end is None:
                continue
            # astimezone() converts UTC-aware datetime to local wall-clock
            local_start = start.astimezone()
            local_end = end.astimezone()
            if local_start.date() != local_end.date():
                # Skip multi-day events
                continue
            date_key = local_start.strftime("%Y-%m-%d")
            times.append((
                date_key,
                local_start.hour, local_start.minute,
                local_end.hour, local_end.minute,
            ))

        return times

    # ------------------------------------------------------------------
    # Statistical inference
    # ------------------------------------------------------------------

    def _infer_windows(
        self,
        event_times: list[tuple[str, int, int, int, int]],
    ) -> Optional[dict]:
        """Infer lunch and dinner windows from event time distribution.

        Returns {"lunch": [h_start, m_start, h_end, m_end], "dinner": [...]}
        or None if both periods fall back to defaults.
        """
        lunch = self._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )
        dinner = self._find_meal_window_in_range(
            event_times,
            range_start_h=17,
            range_end_h=22,
            default=_DEFAULT_DINNER,
        )
        return {"lunch": list(lunch), "dinner": list(dinner)}

    def _find_meal_window_in_range(
        self,
        event_times: list[tuple[str, int, int, int, int]],
        range_start_h: int,
        range_end_h: int,
        default: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        """Find the free-slot window within a given hour range.

        Algorithm:
          1. Group events by calendar date (date_key).
          2. For each day, collect events whose start falls inside
             [range_start_h, range_end_h), sort by start time.
          3. Find intra-day gaps between consecutive events where
             gap >= _MIN_GAP_MINUTES.
          4. Aggregate free-slot start/end minutes across all days.
          5. Return median start/end; fall back to *default* if
             < _MIN_SLOT_SAMPLES gaps collected.
        """
        def to_minutes(h: int, m: int) -> int:
            return h * 60 + m

        range_start_min = to_minutes(range_start_h, 0)
        range_end_min = to_minutes(range_end_h, 0)

        # Group by calendar date
        by_date: dict[str, list[tuple[int, int, int, int]]] = {}
        for date_key, sh, sm, eh, em in event_times:
            if to_minutes(sh, sm) >= range_start_min and to_minutes(sh, sm) < range_end_min:
                by_date.setdefault(date_key, []).append((sh, sm, eh, em))

        if not by_date:
            return default

        free_starts: list[int] = []
        free_ends: list[int] = []

        for day_events in by_date.values():
            # Sort this day's events by start time
            day_sorted = sorted(day_events, key=lambda ev: to_minutes(ev[0], ev[1]))

            # Gap from range_start to first event of the day
            first_start = to_minutes(day_sorted[0][0], day_sorted[0][1])
            if first_start - range_start_min >= _MIN_GAP_MINUTES:
                free_starts.append(range_start_min)
                free_ends.append(first_start)

            # Gaps between consecutive events within the same day
            for i in range(len(day_sorted) - 1):
                curr_end = to_minutes(day_sorted[i][2], day_sorted[i][3])
                next_start = to_minutes(day_sorted[i + 1][0], day_sorted[i + 1][1])
                gap = next_start - curr_end
                if gap >= _MIN_GAP_MINUTES:
                    free_starts.append(curr_end)
                    free_ends.append(next_start)

        if len(free_starts) < _MIN_SLOT_SAMPLES:
            return default

        med_start = int(median(free_starts))
        med_end = int(median(free_ends))

        return (med_start // 60, med_start % 60, med_end // 60, med_end % 60)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _persist_windows(self, family_id: UUID, windows: dict) -> None:
        """Upsert inferred_meal_windows into FamilyPreference."""
        now = utc_now()

        stmt = select(FamilyPreference).where(
            FamilyPreference.family_id == family_id
        )
        result = await self.db.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref is None:
            pref = FamilyPreference(
                family_id=family_id,
                inferred_meal_windows=windows,
                meal_windows_inferred_at=now,
            )
            self.db.add(pref)
        else:
            pref.inferred_meal_windows = windows
            pref.meal_windows_inferred_at = now

        await self.db.flush()
