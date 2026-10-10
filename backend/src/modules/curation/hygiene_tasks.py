"""
Event Hygiene Scheduled Tasks - Daily cleanup of stale curated data.

Runs daily at 3:00 AM (Celery Beat) to clean up inactive, cancelled,
and dismissed curated events/associations across all families.
"""
import logging
from uuid import UUID

from celery import shared_task

from ...core.scheduler._async_compat import run_async
from ...core.scheduler.reschedule import reschedule_sync
from ...core.utils.timezone import utc_now
from ...db.session import create_celery_async_session
from .task_utils import get_active_families

logger = logging.getLogger(__name__)

DEFAULT_INACTIVE_RETENTION_DAYS = 7
DEFAULT_CANCELLED_RETENTION_DAYS = 30


async def _get_family_hygiene_settings(family_id, session_factory) -> dict:
    """Get hygiene settings for a family."""
    from ..insight.models import UserInsightSettings
    from sqlalchemy import select

    async with session_factory() as db:
        result = await db.execute(
            select(
                UserInsightSettings.hygiene_enabled,
                UserInsightSettings.inactive_retention_days,
                UserInsightSettings.cancelled_retention_days,
            )
            .where(UserInsightSettings.family_id == family_id)
            .limit(1)
        )
        row = result.one_or_none()

        if row is None:
            return {
                "hygiene_enabled": True,
                "inactive_retention_days": DEFAULT_INACTIVE_RETENTION_DAYS,
                "cancelled_retention_days": DEFAULT_CANCELLED_RETENTION_DAYS,
            }

        return {
            "hygiene_enabled": row[0] if row[0] is not None else True,
            "inactive_retention_days": row[1] if row[1] is not None else DEFAULT_INACTIVE_RETENTION_DAYS,
            "cancelled_retention_days": row[2] if row[2] is not None else DEFAULT_CANCELLED_RETENTION_DAYS,
        }


async def _run_daily_hygiene() -> dict:
    """Run hygiene cleanup for all active families."""
    engine, session_factory = create_celery_async_session()
    try:
        families = await get_active_families(session_factory)

        if not families:
            logger.info("No active families for hygiene")
            return {"status": "no_families", "count": 0}

        logger.info("Daily hygiene starting for %d families", len(families))

        results = []
        skipped = 0
        errors = []

        for family_id in families:
            try:
                hygiene_settings = await _get_family_hygiene_settings(family_id, session_factory)

                if not hygiene_settings["hygiene_enabled"]:
                    logger.debug("Hygiene disabled for family %s, skipping", family_id)
                    skipped += 1
                    continue

                async with session_factory() as db:
                    from .services.hygiene_service import EventHygieneService
                    from ...core.llm.haiku_client import get_haiku_client

                    service = EventHygieneService(db, llm_provider=get_haiku_client())
                    report = await service.run_daily_cleanup(
                        family_id=family_id,
                        inactive_retention_days=hygiene_settings["inactive_retention_days"],
                        cancelled_retention_days=hygiene_settings["cancelled_retention_days"],
                    )

                    # Trip gap detection (creates PreparationItems for gaps)
                    trip_gaps = await service.detect_trip_gaps(family_id)
                    await db.commit()

                    result_dict = report.to_dict()
                    result_dict["trip_gaps_detected"] = len(trip_gaps)
                    results.append(result_dict)

            except Exception as e:
                error_msg = f"Hygiene failed for family {family_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

                try:
                    async with session_factory() as db:
                        from .models import HygieneRunLog

                        failed_log = HygieneRunLog(
                            family_id=family_id,
                            status="failed",
                            error_message=str(e),
                            started_at=utc_now(),
                            completed_at=utc_now(),
                        )
                        db.add(failed_log)
                        await db.commit()
                except Exception:
                    logger.error("Failed to persist hygiene error log for family %s", family_id)

        summary = {
            "status": "completed",
            "total_families": len(families),
            "success_count": len(results),
            "skipped_count": skipped,
            "error_count": len(errors),
            "total_inactive_deleted": sum(r["inactive_deleted"] for r in results),
            "total_cancelled_deleted": sum(r["cancelled_deleted"] for r in results),
            "total_dismissed_deleted": sum(r["dismissed_deleted"] for r in results),
            "total_auto_completed": sum(r["auto_completed"] for r in results),
            "total_jobs_purged": sum(r["jobs_purged"] for r in results),
            "total_pending_actions_purged": sum(r.get("pending_actions_purged", 0) for r in results),
            "total_trip_gaps_detected": sum(r.get("trip_gaps_detected", 0) for r in results),
            "errors": errors[:10] if errors else [],
        }

        logger.info(
            "Daily hygiene completed: %d/%d executed, %d skipped",
            summary["success_count"],
            summary["total_families"],
            summary["skipped_count"],
        )

        return summary
    finally:
        await engine.dispose()


@shared_task(name="secretary.daily_hygiene")
def daily_hygiene_task():
    """Celery task to run daily event hygiene for all families."""
    logger.info("Starting daily hygiene task")
    return run_async(_run_daily_hygiene())


@shared_task(name="secretary.run_family_hygiene")
def run_family_hygiene_task(family_id: str):
    """Celery task to run hygiene for a single family."""
    logger.info("Starting hygiene for family %s", family_id)
    try:
        return run_async(_run_single_family_hygiene(family_id))
    finally:
        reschedule_sync("secretary.run_family_hygiene", family_id)


async def _run_single_family_hygiene(family_id_str: str) -> dict:
    """Run hygiene for a single family."""
    family_id = UUID(family_id_str)
    engine, session_factory = create_celery_async_session()
    try:
        hygiene_settings = await _get_family_hygiene_settings(family_id, session_factory)

        if not hygiene_settings["hygiene_enabled"]:
            logger.debug("Hygiene disabled for family %s", family_id)
            return {"family_id": family_id_str, "status": "skipped", "reason": "disabled"}

        async with session_factory() as db:
            from .services.hygiene_service import EventHygieneService
            from ...core.llm.haiku_client import get_haiku_client

            service = EventHygieneService(db, llm_provider=get_haiku_client())
            report = await service.run_daily_cleanup(
                family_id=family_id,
                inactive_retention_days=hygiene_settings["inactive_retention_days"],
                cancelled_retention_days=hygiene_settings["cancelled_retention_days"],
            )

            # Trip gap detection
            trip_gaps = await service.detect_trip_gaps(family_id)
            await db.commit()

            result_dict = report.to_dict()
            result_dict["trip_gaps_detected"] = len(trip_gaps)
            return result_dict
    except Exception as e:
        try:
            async with session_factory() as db:
                from .models import HygieneRunLog

                failed_log = HygieneRunLog(
                    family_id=family_id,
                    status="failed",
                    error_message=str(e),
                    started_at=utc_now(),
                    completed_at=utc_now(),
                )
                db.add(failed_log)
                await db.commit()
        except Exception:
            logger.error("Failed to persist hygiene error log for family %s", family_id)
        raise
    finally:
        await engine.dispose()


__all__ = [
    "daily_hygiene_task",
    "run_family_hygiene_task",
]
