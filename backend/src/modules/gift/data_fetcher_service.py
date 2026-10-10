"""Data fetcher service — external trending gift data ingestion.

Orchestrates scraper execution across active data sources, processes
and upserts fetched gift data, and maintains update logs.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DataSource, GiftCategory, UpdateLog, UpdateStatus
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class DataFetcherService:
    """Service for fetching and updating trending gift data from external scrapers."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._scrapers: Dict[str, Any] = {}

    def register_scraper(self, name: str, scraper):
        """Register a scraper instance."""
        self._scrapers[name] = scraper
        logger.info("Registered scraper: %s", name)

    async def fetch_all_sources(
        self,
        categories: Optional[List[str]] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch data from all active sources."""
        log = await self._create_running_log(task_id)

        total_added = 0
        total_updated = 0
        source_stats: Dict[str, Any] = {}
        errors: List[str] = []

        try:
            sources = await self._get_active_data_sources()

            for source in sources:
                scraper = self._scrapers.get(source.name)
                if not scraper:
                    source_stats[source.name] = {"status": "skipped", "reason": "no_scraper"}
                    continue

                try:
                    start = utc_now()
                    target_cats = categories or [cat.value for cat in GiftCategory]
                    gifts_data: List[Dict[str, Any]] = []

                    for cat in target_cats:
                        try:
                            cat_gifts = await scraper.fetch_category(cat)
                            gifts_data.extend(cat_gifts)
                        except Exception as e:
                            errors.append(f"{source.name}:{cat}: {e}")

                    stats: Dict[str, int] = {"added": 0, "updated": 0}
                    if gifts_data:
                        stats = await self._process_and_save_gifts(gifts_data)
                        total_added += stats["added"]
                        total_updated += stats["updated"]

                    duration_ms = int((utc_now() - start).total_seconds() * 1000)
                    source_stats[source.name] = {
                        "status": "success",
                        "count": len(gifts_data),
                        "added": stats["added"],
                        "updated": stats["updated"],
                        "duration_ms": duration_ms,
                    }
                    source.last_fetch_at = utc_now()
                    source.reset_error_count()

                except Exception as e:
                    source_stats[source.name] = {"status": "failed", "error": str(e)}
                    source.increment_error_count()
                    errors.append(f"{source.name}: {e}")

            await self._finalize_log(log, total_added, total_updated, source_stats, errors)
            await self.session.commit()

            overall = (
                "success"
                if not errors
                else "partial" if total_added + total_updated > 0 else "failed"
            )
            return {
                "status": overall,
                "added": total_added,
                "updated": total_updated,
                "source_stats": source_stats,
                "errors": errors,
            }

        except Exception as e:
            logger.error("Fatal error in fetch_all_sources: %s", e)
            await self._mark_log_failed(log.id, str(e))
            await self.session.commit()
            raise

    async def is_update_running(self) -> bool:
        """Check if an update is currently running."""
        stmt = (
            select(UpdateLog)
            .where(UpdateLog.status == UpdateStatus.RUNNING.value)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def get_last_update_status(self) -> Optional[Dict[str, Any]]:
        """Get the status of the last update."""
        stmt = select(UpdateLog).order_by(desc(UpdateLog.started_at)).limit(1)
        log = (await self.session.execute(stmt)).scalar_one_or_none()
        return log.to_dict() if log else None

    # -- private helpers -------------------------------------------------------

    async def _get_active_data_sources(self) -> List[DataSource]:
        stmt = (
            select(DataSource)
            .where(DataSource.is_active.is_(True))
            .order_by(desc(DataSource.priority))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _process_and_save_gifts(
        self, gifts_data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        from .trending_service import TrendingGiftService
        added = 0
        updated = 0
        trending_svc = TrendingGiftService(self.session)

        for gd in gifts_data:
            if not gd.get("external_id") or not gd.get("data_source"):
                continue
            if gd.get("original_price") and gd.get("price"):
                original = float(gd["original_price"])
                current = float(gd["price"])
                if original > current > 0:
                    gd["discount_percent"] = int((original - current) / original * 100)

            existing = await trending_svc._get_by_external_id(
                gd["external_id"], gd["data_source"]
            )
            await trending_svc._upsert(gd)
            if existing:
                updated += 1
            else:
                added += 1

        return {"added": added, "updated": updated}

    async def _create_running_log(self, task_id: Optional[str] = None) -> UpdateLog:
        log = UpdateLog(
            task_id=task_id,
            started_at=utc_now(),
            status=UpdateStatus.RUNNING.value,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def _finalize_log(
        self,
        log: UpdateLog,
        added: int,
        updated: int,
        source_stats: Dict[str, Any],
        errors: List[str],
    ):
        if not errors:
            log.mark_success(added, updated, 0)
        elif added > 0 or updated > 0:
            log.mark_partial("; ".join(errors), added, updated)
        else:
            log.mark_failed("; ".join(errors))
        log.source_stats = source_stats
        await self.session.flush()

    async def _mark_log_failed(self, log_id: UUID, error_message: str):
        stmt = select(UpdateLog).where(UpdateLog.id == log_id)
        log = (await self.session.execute(stmt)).scalar_one_or_none()
        if log:
            log.mark_failed(error_message)
            await self.session.flush()
