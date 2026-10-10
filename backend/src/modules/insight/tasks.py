"""Insight Celery Tasks — Scheduled insight generation, hygiene, cascade recheck,
four-wave delivery dispatch, and L3 deep reasoning.

Task names:
  - secretary.generate_daily_insights   (daily 06:00 UTC via unified dispatcher)
  - secretary.insight_hygiene_cleanup   (daily 04:00 UTC + every 6h)
  - secretary.recheck_cascade_skipped   (delayed 5 min, triggered by cascade)
  - secretary.dispatch_wave_delivery    (beat: 07/12/17/21 UTC; fan-out per user)
  - secretary.deliver_insight_wave      (per-user wave delivery, called by dispatcher)
  - secretary.generate_deep_insights    (post-pipeline L3 Sonnet deep reasoning)
"""
import dataclasses
import logging
from typing import List
from uuid import UUID

from celery import shared_task

from ...core.scheduler._async_compat import run_async
from ...core.utils.timezone import local_today, utc_now
from ...db.session import create_celery_async_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task 1: Daily insight generation (InsightPipeline.run_scheduled)
# ---------------------------------------------------------------------------


async def _generate_insights_for_user(
    user_id_str: str,
    session_factory,
) -> dict:
    """Generate daily insights for a single user via InsightPipeline."""
    user_id = UUID(user_id_str)

    async with session_factory() as db:
        # Resolve family_id
        from sqlalchemy import select
        from ..member.models.user import User

        result = await db.execute(
            select(User.family_id).where(User.id == user_id)
        )
        family_id = result.scalar_one_or_none()

        if family_id is None:
            logger.warning(
                "User %s has no family, skipping insight generation", user_id_str
            )
            return {"user_id": user_id_str, "status": "skipped", "reason": "no_family"}

    async with session_factory() as db:
        from .insight_pipeline import InsightPipeline

        pipeline = InsightPipeline(db)
        target_date = local_today()

        try:
            insight_ids = await pipeline.run_scheduled(
                user_id=user_id,
                family_id=family_id,
                target_date=target_date,
            )
            await db.commit()

            return {
                "user_id": user_id_str,
                "status": "completed",
                "insights_generated": len(insight_ids),
                "date": str(target_date),
            }
        except Exception as e:
            logger.error(
                "Insight generation failed for user %s: %s", user_id_str, e,
                exc_info=True,
            )
            return {
                "user_id": user_id_str,
                "status": "failed",
                "error": str(e),
            }


async def _generate_all_daily_insights() -> dict:
    """Generate daily insights for all active users."""
    engine, session_factory = create_celery_async_session()
    try:
        # Get active users
        async with session_factory() as db:
            from sqlalchemy import select
            from ..member.models.user import User

            result = await db.execute(
                select(User.id).where(User.is_active.is_(True))
            )
            user_ids = [str(row[0]) for row in result.all()]

        if not user_ids:
            logger.info("No active users for daily insight generation")
            return {"status": "no_users", "count": 0}

        logger.info(
            "Daily insight generation starting for %d users", len(user_ids)
        )

        results = []
        errors = []

        for uid_str in user_ids:
            try:
                result = await _generate_insights_for_user(uid_str, session_factory)
                results.append(result)
            except Exception as e:
                error_msg = f"Insight generation failed for user {uid_str}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        summary = {
            "status": "completed",
            "total_users": len(user_ids),
            "success_count": sum(
                1 for r in results if r.get("status") == "completed"
            ),
            "skipped_count": sum(
                1 for r in results if r.get("status") == "skipped"
            ),
            "error_count": len(errors),
            "total_insights": sum(
                r.get("insights_generated", 0) for r in results
            ),
            "errors": errors[:10] if errors else [],
        }

        logger.info(
            "Daily insight generation completed: %d/%d successful, %d insights total",
            summary["success_count"],
            summary["total_users"],
            summary["total_insights"],
        )

        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.generate_daily_insights",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def generate_daily_insights_task(self):
    """Celery task: generate daily insights for all active users.

    Scheduled via Celery Beat at 06:00 UTC. Calls
    InsightPipeline.run_scheduled() for each active user.
    """
    logger.info("Starting daily insight generation task")
    return run_async(_generate_all_daily_insights())


# ---------------------------------------------------------------------------
# Task 2: Insight hygiene cleanup (InsightHygiene.run_cleanup)
# ---------------------------------------------------------------------------


async def _run_insight_hygiene() -> dict:
    """Run insight hygiene cleanup (expiry, orphans, archive)."""
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from .insight_hygiene import InsightHygiene

            hygiene = InsightHygiene(db)
            summary = await hygiene.run_cleanup()
            await db.commit()

            logger.info("Insight hygiene cleanup completed: %s", summary)
            return summary
    except Exception as e:
        logger.error("Insight hygiene cleanup failed: %s", e, exc_info=True)
        return {"status": "failed", "error": str(e)}
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.insight_hygiene_cleanup",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def insight_hygiene_cleanup_task(self):
    """Celery task: run insight hygiene cleanup.

    Scheduled at 04:00 UTC daily + every 6h. Handles:
    - Expire stale insights
    - Dismiss orphaned entity references
    - Archive old dismissed/expired insights
    - Obligation coverage audit
    - Recheck expired cascade PendingActions
    """
    logger.info("Starting insight hygiene cleanup task")
    return run_async(_run_insight_hygiene())


# ---------------------------------------------------------------------------
# Task 3: Cascade recheck (delayed, triggered by InsightCascadeService)
# ---------------------------------------------------------------------------


async def _recheck_cascade_skipped(
    trip_id_str: str,
    skipped_ids_str: List[str],
) -> dict:
    """Recheck insights that were skipped (SKIP LOCKED) during cascade.

    Attempts to acquire row locks on the previously-skipped insight IDs
    and re-runs the cascade classification + action for each.
    """
    trip_id = UUID(trip_id_str)
    skipped_ids = [UUID(sid) for sid in skipped_ids_str]

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from sqlalchemy import select
            from .models import Insight, InsightStatus
            from .insight_cascade_service import InsightCascadeService

            cascade = InsightCascadeService(db)
            now = utc_now()

            processed = 0
            still_locked = 0

            for insight_id in skipped_ids:
                try:
                    # Try to acquire lock (skip if still locked)
                    result = await db.execute(
                        select(Insight)
                        .where(Insight.id == insight_id)
                        .with_for_update(skip_locked=True)
                    )
                    insight = result.scalar_one_or_none()

                    if insight is None:
                        still_locked += 1
                        continue

                    # Skip if already in terminal state (handled by another path)
                    if insight.status in (
                        InsightStatus.ACTED.value,
                        InsightStatus.DISMISSED.value,
                        InsightStatus.EXPIRED.value,
                    ):
                        processed += 1
                        continue

                    # Re-run classification and apply action
                    classification = cascade._classify_on_cancel(insight)
                    if classification == "preserve_as_action":
                        await cascade._convert_to_pending_action(insight, trip_id)
                        insight.status = InsightStatus.ACTED.value
                        insight.acted_at = now
                    elif classification == "preserve_as_note":
                        await cascade._convert_to_secretary_note(insight)
                        insight.status = InsightStatus.DISMISSED.value
                        insight.dismissed_at = now
                    else:
                        insight.status = InsightStatus.DISMISSED.value
                        insight.dismissed_at = now

                    processed += 1

                except Exception as e:
                    logger.warning(
                        "Recheck failed for insight %s: %s", insight_id, e,
                    )
                    still_locked += 1

            await db.commit()

            summary = {
                "trip_id": trip_id_str,
                "total_skipped": len(skipped_ids),
                "processed": processed,
                "still_locked": still_locked,
            }

            logger.info("Cascade recheck completed: %s", summary)
            return summary
    except Exception as e:
        logger.error(
            "Cascade recheck failed for trip %s: %s", trip_id_str, e,
            exc_info=True,
        )
        return {
            "trip_id": trip_id_str,
            "status": "failed",
            "error": str(e),
        }
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.recheck_cascade_skipped",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=3,
    default_retry_delay=60,
)
def recheck_cascade_skipped_task(self, trip_id: str, skipped_ids: List[str]):
    """Celery task: recheck insights skipped during cascade (SKIP LOCKED).

    Triggered by InsightCascadeService with a 5-minute countdown delay.
    Retries up to 3 times with 60s delay between retries.
    """
    logger.info(
        "Starting cascade recheck: trip=%s, skipped=%d",
        trip_id, len(skipped_ids),
    )
    return run_async(_recheck_cascade_skipped(trip_id, skipped_ids))


# ---------------------------------------------------------------------------
# Task 4: Wave delivery — per-user (called by dispatch_wave_delivery)
# ---------------------------------------------------------------------------

from .delivery_timing_engine import _WAVE_BY_NAME

_VALID_WAVES = frozenset(_WAVE_BY_NAME.keys())


async def _deliver_wave_for_user(
    user_id_str: str,
    wave_name: str,
    session_factory,
) -> dict:
    """Deliver insights for one wave to a single user.

    Uses InsightQueryService.get_for_wave() which filters by the wave's
    focus_types so each wave surfaces only contextually relevant content.
    """
    from uuid import UUID

    user_id = UUID(user_id_str)

    async with session_factory() as db:
        from sqlalchemy import select
        from ..member.models.user import User

        # Resolve family_id
        result = await db.execute(
            select(User.family_id).where(User.id == user_id)
        )
        family_id = result.scalar_one_or_none()

        if family_id is None:
            logger.warning(
                "Wave delivery: user %s has no family, skipping", user_id_str
            )
            return {"user_id": user_id_str, "wave": wave_name, "status": "skipped", "reason": "no_family"}

        # Load user-custom delivery_waves; graceful degradation on any error
        from .insight_settings_model import UserInsightSettings

        user_delivery_waves = None
        try:
            settings_result = await db.execute(
                select(UserInsightSettings.delivery_waves).where(
                    UserInsightSettings.user_id == user_id
                )
            )
            user_delivery_waves = settings_result.scalar_one_or_none()
        except Exception as exc:
            logger.warning(
                "Wave delivery: could not load delivery_waves for user %s, "
                "falling back to defaults: %s",
                user_id_str, exc,
            )

        # Resolve effective wave config (user overrides hour/max_items; focus_types unchanged)
        from .delivery_timing_engine import DeliveryTimingEngine

        engine_instance = DeliveryTimingEngine()
        try:
            wave_cfg = engine_instance.get_wave_config(wave_name, user_delivery_waves)
        except ValueError:
            logger.error(
                "Wave delivery: unknown wave_name=%r for user %s, aborting",
                wave_name, user_id_str,
            )
            return {
                "user_id": user_id_str,
                "wave": wave_name,
                "status": "error",
                "reason": f"unknown wave '{wave_name}'",
            }

        max_items = wave_cfg.max_items

        from .insight_query_service import InsightQueryService

        svc = InsightQueryService(db)
        try:
            cards = await svc.get_for_wave(
                user_id=user_id,
                family_id=family_id,
                wave_name=wave_name,
                limit=max_items,
            )
        except Exception as exc:
            logger.error(
                "Wave delivery query failed for user %s wave %s: %s",
                user_id_str, wave_name, exc,
                exc_info=True,
            )
            return {
                "user_id": user_id_str,
                "wave": wave_name,
                "status": "failed",
                "error": str(exc),
            }

        await db.commit()

    logger.info(
        "Wave delivery: user=%s wave=%s delivered=%d cards",
        user_id_str, wave_name, len(cards),
    )
    return {
        "user_id": user_id_str,
        "wave": wave_name,
        "status": "delivered",
        "cards_delivered": len(cards),
    }


@shared_task(
    name="secretary.deliver_insight_wave",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def deliver_insight_wave_task(self, user_id: str, wave_name: str):
    """Celery task: deliver insights for one wave to a single user.

    Called by ``dispatch_wave_delivery_task`` once per active user per wave.
    ``wave_name`` must be one of: morning, noon, evening, night.
    """
    if wave_name not in _VALID_WAVES:
        logger.error("deliver_insight_wave: unknown wave_name=%r, aborting", wave_name)
        return {"status": "error", "reason": f"unknown wave '{wave_name}'"}

    logger.info("Starting wave delivery: user=%s wave=%s", user_id, wave_name)
    engine, session_factory = create_celery_async_session()
    try:
        return run_async(_deliver_wave_for_user(user_id, wave_name, session_factory))
    finally:
        run_async(engine.dispose())


# ---------------------------------------------------------------------------
# Task 5: Wave dispatch — fan-out to all active users (beat-triggered)
# ---------------------------------------------------------------------------


async def _dispatch_wave_delivery(wave_name: str) -> dict:
    """Fan out deliver_insight_wave tasks to all users who have insights enabled."""
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from sqlalchemy import select
            from .insight_settings_model import UserInsightSettings

            result = await db.execute(
                select(UserInsightSettings.user_id).where(
                    UserInsightSettings.hygiene_enabled.is_(True)
                )
            )
            user_ids = [str(row[0]) for row in result.all()]

        if not user_ids:
            logger.info("dispatch_wave_delivery(%s): no active users", wave_name)
            return {"wave": wave_name, "status": "no_users", "count": 0}

        for uid_str in user_ids:
            deliver_insight_wave_task.delay(uid_str, wave_name)

        logger.info(
            "dispatch_wave_delivery(%s): dispatched %d user tasks",
            wave_name, len(user_ids),
        )
        return {"wave": wave_name, "status": "dispatched", "user_count": len(user_ids)}
    except Exception as exc:
        logger.error(
            "dispatch_wave_delivery(%s) failed: %s", wave_name, exc, exc_info=True
        )
        return {"wave": wave_name, "status": "failed", "error": str(exc)}
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.dispatch_wave_delivery",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=60,
)
def dispatch_wave_delivery_task(self, wave_name: str):
    """Celery task: fan out wave delivery to all active users.

    Scheduled via Celery Beat at 07:00, 12:00, 17:00, 21:00 UTC for
    morning/noon/evening/night waves respectively. Fetches users from
    UserInsightSettings (hygiene_enabled=True as a proxy for active users)
    and dispatches one deliver_insight_wave task per user.
    """
    if wave_name not in _VALID_WAVES:
        logger.error("dispatch_wave_delivery: unknown wave_name=%r, aborting", wave_name)
        return {"status": "error", "reason": f"unknown wave '{wave_name}'"}

    logger.info("Starting wave dispatch: wave=%s", wave_name)
    return run_async(_dispatch_wave_delivery(wave_name))


# ---------------------------------------------------------------------------
# Task 6: Implicit feedback — stale view detection (daily)
# ---------------------------------------------------------------------------


async def _process_implicit_feedback_all_users() -> dict:
    """Process implicit feedback (stale views) for all active users."""
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from sqlalchemy import select
            from ..member.models.user import User

            result = await db.execute(
                select(User.id).where(User.is_active.is_(True))
            )
            user_ids = [row[0] for row in result.all()]

        if not user_ids:
            logger.info("No active users for implicit feedback processing")
            return {"status": "no_users", "count": 0}

        total_processed = 0
        errors = []

        for uid in user_ids:
            try:
                async with session_factory() as db:
                    from .implicit_feedback import ImplicitFeedbackCollector

                    collector = ImplicitFeedbackCollector(db)
                    count = await collector.process_stale_views(uid)
                    await db.commit()
                    total_processed += count
            except Exception as e:
                error_msg = f"Implicit feedback failed for user {uid}: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        summary = {
            "status": "completed",
            "total_users": len(user_ids),
            "total_processed": total_processed,
            "error_count": len(errors),
            "errors": errors[:10] if errors else [],
        }

        logger.info(
            "Implicit feedback processing completed: %d signals from %d users",
            total_processed, len(user_ids),
        )
        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.process_implicit_feedback",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def process_implicit_feedback_task(self):
    """Celery task: process implicit feedback for all active users.

    Scheduled daily at 05:00 UTC. Detects insights that were viewed
    but never acted upon (stale views) and records them as weak-negative
    preference signals for downstream preference extraction.
    """
    logger.info("Starting implicit feedback processing task")
    return run_async(_process_implicit_feedback_all_users())


# ---------------------------------------------------------------------------
# Task 7: L3 deep reasoning (post-pipeline, async via Celery)
# ---------------------------------------------------------------------------


async def _generate_deep_insights(
    user_id_str: str,
    family_id_str: str,
    target_date_str: str,
) -> dict:
    """Run L3 Sonnet deep reasoning for a single user.

    Re-collects signals (since AllSignals is not serializable across
    the Celery boundary), identifies cross-signal patterns, and persists
    L3 insights with ``deep:`` dedup key prefix.
    """
    from datetime import date as date_type
    from uuid import UUID as UUID_type, uuid4

    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from .deep_reasoning_engine import DeepReasoningEngine
    from .insight_signal_collector import InsightSignalCollector
    from sqlalchemy import select
    from .models import (
        GenerationLevel,
        Insight,
        InsightCandidate,
        InsightEntity,
        InsightStatus,
    )
    from .expiry_policy import compute_expires_at

    user_id = UUID_type(user_id_str)
    family_id = UUID_type(family_id_str)
    target_date = date_type.fromisoformat(target_date_str)

    engine_db, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            # Re-collect signals for deep analysis
            collector = InsightSignalCollector(db)
            signals = await collector.collect_all(
                user_id=user_id,
                family_id=family_id,
                target_date=target_date,
            )

            if signals.total_count() < 3:
                logger.info(
                    "L3 deep reasoning: insufficient signals (%d) for user %s",
                    signals.total_count(), user_id_str,
                )
                return {
                    "user_id": user_id_str,
                    "status": "skipped",
                    "reason": "insufficient_signals",
                }

            # Query existing L1/L2 insights to avoid semantic duplication
            from datetime import datetime, timezone
            from sqlalchemy import and_

            existing_stmt = (
                select(Insight.insight_type, Insight.title, Insight.dedup_key)
                .where(
                    and_(
                        Insight.user_id == user_id,
                        Insight.created_at >= datetime.combine(
                            target_date, datetime.min.time(), tzinfo=timezone.utc,
                        ),
                        Insight.status.in_([
                            InsightStatus.PENDING.value,
                            InsightStatus.ACTIVE.value,
                        ]),
                    )
                )
            )
            existing_result = await db.execute(existing_stmt)
            existing_candidates = [
                InsightCandidate(
                    insight_type=row[0],
                    title=row[1],
                    content="",
                    dedup_key=row[2] or "",
                )
                for row in existing_result.all()
            ]

            # Run deep reasoning engine
            reasoning_engine = DeepReasoningEngine(target_date=target_date)
            candidates = await reasoning_engine.analyze(
                signals=signals,
                existing_candidates=existing_candidates or None,
            )

            if not candidates:
                logger.info(
                    "L3 deep reasoning: no candidates for user %s", user_id_str,
                )
                return {
                    "user_id": user_id_str,
                    "status": "no_candidates",
                    "insights_generated": 0,
                }

            # Stamp user_id / family_id on all candidates
            candidates = [
                dataclasses.replace(c, user_id=user_id, family_id=family_id)
                for c in candidates
            ]

            # Persist L3 insights (includes generation_level, context_hint)
            now = utc_now()
            inserted_ids: List[UUID_type] = []

            for c in candidates:
                insight_id = uuid4()

                expires = (
                    c.expires_at
                    if c.expires_at is not None
                    else compute_expires_at(
                        c.insight_type,
                        action_data=c.source_context,
                    )
                )

                source = c.source_context.get("_source", "scheduled")
                persisted_context = {
                    k: v for k, v in c.source_context.items() if k != "_source"
                }

                stmt = pg_insert(Insight).values(
                    id=insight_id,
                    user_id=c.user_id,
                    family_id=c.family_id,
                    insight_type=c.insight_type,
                    title=c.title,
                    content=c.content,
                    importance=c.importance,
                    urgency=c.urgency,
                    status=InsightStatus.PENDING.value,
                    source=source,
                    suggested_action=c.suggested_action,
                    action_options=c.action_options,
                    source_context=persisted_context or None,
                    feedback_source="system",
                    dedup_key=c.dedup_key or None,
                    expires_at=expires,
                    created_at=now,
                    generation_level=GenerationLevel.L3_SONNET.value,
                    context_hint=c.context_hint,
                    best_action_window=c.best_action_window,
                ).on_conflict_do_nothing(
                    index_elements=["user_id", "dedup_key"],
                    index_where=text(
                        "dedup_key IS NOT NULL "
                        "AND status NOT IN ('dismissed', 'acted', 'expired')"
                    ),
                )

                result = await db.execute(stmt)
                if result.rowcount > 0:
                    inserted_ids.append(insight_id)

                    # Create InsightEntity rows
                    all_entities: List[dict] = []
                    seen_keys: set = set()
                    for spec in c.entities:
                        if not spec.entity_id:
                            continue
                        try:
                            eid = (
                                UUID_type(spec.entity_id)
                                if not isinstance(spec.entity_id, UUID_type)
                                else spec.entity_id
                            )
                        except (ValueError, AttributeError):
                            continue
                        role = (
                            spec.role
                            if spec.role in (
                                "primary", "related", "mentioned", "source",
                            )
                            else "related"
                        )
                        key = (spec.entity_type, eid)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_entities.append({
                                "insight_id": insight_id,
                                "entity_type": spec.entity_type,
                                "entity_id": eid,
                                "role": role,
                            })

                    if all_entities:
                        await db.execute(
                            pg_insert(InsightEntity)
                            .values(all_entities)
                            .on_conflict_do_nothing()
                        )

            if inserted_ids:
                await db.flush()

            await db.commit()

            logger.info(
                "L3 deep reasoning: user=%s candidates=%d persisted=%d",
                user_id_str, len(candidates), len(inserted_ids),
            )

            return {
                "user_id": user_id_str,
                "status": "completed",
                "insights_generated": len(inserted_ids),
                "date": target_date_str,
            }

    except Exception as e:
        logger.error(
            "L3 deep reasoning failed for user %s: %s",
            user_id_str, e, exc_info=True,
        )
        return {
            "user_id": user_id_str,
            "status": "failed",
            "error": str(e),
        }
    finally:
        await engine_db.dispose()


@shared_task(
    name="secretary.generate_deep_insights",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=1,
    default_retry_delay=60,
)
def generate_deep_insights_task(
    self,
    user_id: str,
    family_id: str,
    target_date: str,
):
    """Celery task: L3 Sonnet deep reasoning for a single user.

    Queued by InsightPipeline.run_scheduled() after L1/L2 persist.
    Runs asynchronously — does not block the main pipeline.
    """
    logger.info(
        "Starting L3 deep reasoning: user=%s date=%s",
        user_id, target_date,
    )
    return run_async(_generate_deep_insights(user_id, family_id, target_date))


# ---------------------------------------------------------------------------
# Task 8: Entity link backfill repair (daily at 04:45 UTC)
# ---------------------------------------------------------------------------


async def _repair_entity_links() -> dict:
    """Repair insights with zero InsightEntity rows via signal-driven synthesis."""
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from .insight_hygiene import InsightHygiene

            hygiene = InsightHygiene(db)
            summary = await hygiene.repair_entity_links()
            await db.commit()

            logger.info("Entity link repair completed: %s", summary)
            return summary
    except Exception as e:
        logger.error("Entity link repair failed: %s", e, exc_info=True)
        return {"status": "failed", "error": str(e)}
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.repair_entity_links",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def repair_entity_links_task(self):
    """Celery task: repair insights with zero entity links.

    Scheduled daily at 04:45 UTC. Synthesizes entity links from
    source_context signal_ids for insights that have zero InsightEntity
    rows. Additive-only — does not change insight status or content.
    """
    logger.info("Starting entity link repair task")
    return run_async(_repair_entity_links())


# ---------------------------------------------------------------------------
# Task 9: Weekly insight self-report (M4 Secretary Self-Model)
# ---------------------------------------------------------------------------


async def _generate_insight_self_report() -> dict:
    """Generate M4 self-model report for all active families."""
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from sqlalchemy import select
            from ..member.models.user import User

            result = await db.execute(
                select(User.family_id)
                .where(User.is_active.is_(True))
                .distinct()
            )
            family_ids = [row[0] for row in result.all() if row[0] is not None]

        if not family_ids:
            logger.info("No active families for self-report generation")
            return {"status": "no_families", "count": 0}

        reports_generated = 0
        declining_summary: List[str] = []

        for fam_id in family_ids:
            try:
                async with session_factory() as db:
                    from .insight_self_model import generate_self_report

                    report = await generate_self_report(db, fam_id)

                    reports_generated += 1
                    if report.declining_types:
                        declining_summary.append(
                            f"family={fam_id}: declining={report.declining_types}"
                        )

                    logger.info(
                        "Self-report: family=%s declining=%s best=%s",
                        fam_id,
                        report.declining_types,
                        report.best_performing_types,
                    )
            except Exception as exc:
                logger.error(
                    "Self-report failed for family %s: %s",
                    fam_id, exc, exc_info=True,
                )

        summary = {
            "status": "completed",
            "families_processed": reports_generated,
            "families_with_declining": len(declining_summary),
            "declining_details": declining_summary[:10],
        }
        logger.info("Weekly self-report completed: %s", summary)
        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.generate_insight_self_report",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=60,
)
def generate_insight_self_report_task(self):
    """Celery task: weekly M4 secretary self-model report.

    Scheduled via Celery Beat at 04:00 UTC on Mondays. Generates
    self-performance reports comparing 7d vs 30d insight accuracy
    by type, identifies declining types, and logs recommendations.
    Weight adjustments are applied in real-time by the pipeline.
    """
    logger.info("Starting weekly insight self-report generation")
    return run_async(_generate_insight_self_report())


__all__ = [
    "generate_daily_insights_task",
    "insight_hygiene_cleanup_task",
    "recheck_cascade_skipped_task",
    "deliver_insight_wave_task",
    "dispatch_wave_delivery_task",
    "process_implicit_feedback_task",
    "generate_deep_insights_task",
    "repair_entity_links_task",
    "generate_insight_self_report_task",
]
