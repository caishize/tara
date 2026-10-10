"""Price tracker — monitors prices for gift tasks and generates alerts.

Delegates to modules/gift/providers/ for actual price fetching.
Stores tracked items and their price history in the gift_tasks JSONB fields.
"""
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import GiftTask, TaskStatus
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

# Price drop thresholds for alerting
ALERT_THRESHOLD_PERCENT = 10  # Alert if price drops >= 10%


class PriceAlert:
    """Represents a price drop alert."""

    __slots__ = ("gift_task_id", "product_url", "old_price", "new_price", "drop_percent", "checked_at")

    def __init__(
        self,
        gift_task_id: UUID,
        product_url: str,
        old_price: float,
        new_price: float,
        drop_percent: float,
        checked_at: str,
    ):
        self.gift_task_id = gift_task_id
        self.product_url = product_url
        self.old_price = old_price
        self.new_price = new_price
        self.drop_percent = drop_percent
        self.checked_at = checked_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gift_task_id": str(self.gift_task_id),
            "product_url": self.product_url,
            "old_price": self.old_price,
            "new_price": self.new_price,
            "drop_percent": round(self.drop_percent, 1),
            "checked_at": self.checked_at,
        }


class PriceTrackerService:
    """Service for tracking prices of gift task items.

    Tracks prices by storing a `tracked_prices` list in GiftTask.metadata JSONB:
        [{"url": "...", "initial_price": 299.0, "last_price": 279.0, "last_checked": "..."}]
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def track_price(self, gift_task_id: UUID, url: str) -> None:
        """Start tracking price for a gift task item."""
        task = await self._get_task(gift_task_id)
        if not task:
            raise ValueError(f"GiftTask {gift_task_id} not found")

        metadata = dict(task.metadata or {})
        tracked: List[Dict[str, Any]] = list(metadata.get("tracked_prices", []))

        # Avoid duplicate tracking
        if any(t["url"] == url for t in tracked):
            return

        tracked.append({
            "url": url,
            "initial_price": None,
            "last_price": None,
            "last_checked": None,
        })
        metadata["tracked_prices"] = tracked
        task.metadata = metadata
        await self.session.flush()

    async def check_prices(self) -> List[Dict[str, Any]]:
        """Check prices for all tracked items across active gift tasks.

        Returns list of price alerts (significant drops).
        """
        tasks = await self._get_tasks_with_tracking()
        alerts: List[PriceAlert] = []
        now_iso = utc_now().isoformat()

        for task in tasks:
            metadata = dict(task.metadata or {})
            tracked: List[Dict[str, Any]] = list(metadata.get("tracked_prices", []))
            changed = False

            for item in tracked:
                url = item.get("url", "")
                if not url:
                    continue

                try:
                    new_price = await self._fetch_price(url)
                except Exception as e:
                    logger.warning("Price fetch failed for %s: %s", url, e)
                    continue

                if new_price is None or new_price <= 0:
                    continue

                old_price = item.get("last_price")
                if item.get("initial_price") is None:
                    item["initial_price"] = new_price

                item["last_price"] = new_price
                item["last_checked"] = now_iso
                changed = True

                # Check for price drop alert
                if old_price and old_price > 0 and new_price < old_price:
                    drop_pct = ((old_price - new_price) / old_price) * 100
                    if drop_pct >= ALERT_THRESHOLD_PERCENT:
                        alerts.append(
                            PriceAlert(
                                gift_task_id=task.id,
                                product_url=url,
                                old_price=old_price,
                                new_price=new_price,
                                drop_percent=drop_pct,
                                checked_at=now_iso,
                            )
                        )

            if changed:
                metadata["tracked_prices"] = tracked
                task.metadata = metadata

        if tasks:
            await self.session.flush()

        return [a.to_dict() for a in alerts]

    async def get_tracked_items(self, gift_task_id: UUID) -> List[Dict[str, Any]]:
        """Get tracked price items for a gift task."""
        task = await self._get_task(gift_task_id)
        if not task:
            return []
        return list((task.metadata or {}).get("tracked_prices", []))

    async def untrack_price(self, gift_task_id: UUID, url: str) -> bool:
        """Stop tracking a specific URL for a gift task."""
        task = await self._get_task(gift_task_id)
        if not task:
            return False

        metadata = dict(task.metadata or {})
        tracked: List[Dict[str, Any]] = list(metadata.get("tracked_prices", []))
        original_len = len(tracked)
        tracked = [t for t in tracked if t.get("url") != url]

        if len(tracked) == original_len:
            return False

        metadata["tracked_prices"] = tracked
        task.metadata = metadata
        await self.session.flush()
        return True

    # ── private helpers ──────────────────────────────────────────────────

    async def _get_task(self, task_id: UUID) -> Optional[GiftTask]:
        stmt = select(GiftTask).where(GiftTask.id == task_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_tasks_with_tracking(self) -> List[GiftTask]:
        """Get active gift tasks that have tracked prices."""
        active_statuses = [
            TaskStatus.PENDING.value,
            TaskStatus.SCHEDULED.value,
            TaskStatus.COMPLETED.value,
        ]
        stmt = (
            select(GiftTask)
            .where(
                and_(
                    GiftTask.status.in_(active_statuses),
                    GiftTask.metadata.isnot(None),
                )
            )
        )
        tasks = list((await self.session.execute(stmt)).scalars().all())
        # Filter in Python since JSONB key check varies by dialect
        return [t for t in tasks if (t.metadata or {}).get("tracked_prices")]

    async def _fetch_price(self, url: str) -> Optional[float]:
        """Fetch current price for a URL using the core price provider."""
        try:
            from .providers import create_price_service
            service = create_price_service()
            price_data = await service.get_price(url)
            return price_data.current_price
        except ImportError:
            logger.warning("Price provider module not available")
            return None
        except Exception as e:
            logger.warning("Price fetch error for %s: %s", url, e)
            return None
