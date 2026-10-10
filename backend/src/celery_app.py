"""
Celery Application Configuration
Configures Celery for background tasks and scheduled jobs (T016, T019, T032, T033)

Architecture:
- Per-entity tasks (briefing, insights, curation, hygiene, etc.) are scheduled
  via Redis Sorted Sets and dispatched by the unified dispatcher every 30s.
- Global tasks (cache warmup, assistant cleanup, etc.) stay on Celery Beat.
"""
import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import beat_init, worker_process_init, worker_process_shutdown

from .core.utils.timezone import DEFAULT_TIMEZONE_NAME

logger = logging.getLogger(__name__)

# Redis connection (default to localhost if not configured)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "secretary",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        # Unified gift module
        "src.modules.gift.tasks",
        # Curation tasks (secretary.daily_curation, secretary.curate_family, etc.)
        "src.modules.curation.tasks",
        # Hygiene tasks (secretary.daily_hygiene, secretary.run_family_hygiene)
        "src.modules.curation.hygiene_tasks",
        # Briefing tasks (secretary.prepare_daily_content, secretary.generate_daily_briefings)
        "src.modules.briefing.tasks",
        # Insight tasks (secretary.generate_daily_insights, secretary.insight_hygiene_cleanup, etc.)
        "src.modules.insight.tasks",
        # Memory tasks (assistant.* insight/consolidation/compression/cache tasks)
        "src.modules.memory.tasks",
        # Conversation tasks (assistant.expire_stale_pending_actions)
        "src.modules.conversation.tasks",
        # Unified dispatcher
        "src.core.scheduler.dispatcher",
        # Outbox relay
        "src.core.events.outbox_relay",
        # Date management tasks (reminder.send_single, scheduler.holiday_sync/preparation)
        "src.modules.date_manager.tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone=DEFAULT_TIMEZONE_NAME,
    enable_utc=True,

    # Task settings
    task_soft_time_limit=3600,  # 1 hour soft limit
    task_time_limit=3900,  # 1 hour 5 minutes hard limit
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,

    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time
    worker_concurrency=2,  # 2 workers

    # Retry settings
    broker_connection_retry_on_startup=True,

    # Beat schedule - scheduled tasks
    beat_schedule={
        # ============ Outbox Relay (every 5s) ============
        "outbox-relay": {
            "task": "events.relay_outbox",
            "schedule": 5.0,
            "options": {"queue": "default"},
        },

        # ============ Unified Dispatcher (every 30s) ============
        # Pops due entities from Redis sorted sets and dispatches
        # per-entity Celery tasks for: briefing, insights, curation,
        # hygiene, reminders, price checks, gift tasks.
        "unified-dispatch": {
            "task": "scheduler.dispatch",
            "schedule": 30.0,
            "options": {"queue": "default"},
        },

        # ============ Migrated from In-process Schedulers ============

        # Holiday sync (daily at 00:00)
        "holiday-sync": {
            "task": "scheduler.holiday_sync",
            "schedule": crontab(hour=0, minute=0),
        },

        # Holiday preparation (daily at 06:00, after sync)
        "holiday-preparation": {
            "task": "scheduler.holiday_preparation",
            "schedule": crontab(hour=6, minute=0),
        },

        # Gift: expire old tasks (daily at 03:00)
        "gift-expire-old": {
            "task": "gift.expire_old_tasks",
            "schedule": crontab(hour=3, minute=0),
        },

        # Gift: decay preferences (weekly Sunday 04:00)
        "gift-decay-preferences": {
            "task": "gift.decay_preferences",
            "schedule": crontab(hour=4, minute=0, day_of_week=0),
        },

        # Gift: retry failed tasks (daily at 05:00)
        "gift-retry-failed": {
            "task": "gift.retry_failed_tasks",
            "schedule": crontab(hour=5, minute=0),
        },

        # ============ Global Assistant Tasks (no per-entity) ============

        "expired-insights-cleanup": {
            "task": "assistant.cleanup_expired_insights",
            "schedule": crontab(hour=4, minute=0),
            "options": {"queue": "assistant"},
        },

        "daily-memory-compression": {
            "task": "assistant.compress_daily_memories",
            "schedule": crontab(hour=4, minute=30),
            "options": {"queue": "assistant"},
        },

        "extraction-cache-warmup": {
            "task": "assistant.warmup_extraction_cache",
            "schedule": crontab(hour=5, minute=30),
            "options": {"queue": "assistant"},
        },

        "extraction-cache-cleanup-weekly": {
            "task": "assistant.cleanup_extraction_cache",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),
            "options": {"queue": "assistant"},
        },

        # ============ DirtyBit Patrol (every 5 min) ============
        "patrol-dirty-timers": {
            "task": "secretary.patrol_dirty_timers",
            "schedule": 300.0,
            "options": {"queue": "secretary"},
        },

        # ============ PendingAction Lifecycle ============

        "expire-stale-pending-actions": {
            "task": "assistant.expire_stale_pending_actions",
            "schedule": crontab(minute="*/2"),
            "options": {"queue": "assistant"},
        },

        # ============ T0 Proactive Trigger Scan (daily at 08:00) ============
        "proactive-trigger-scan": {
            "task": "secretary.proactive_scan",
            "schedule": crontab(hour=8, minute=0),
            "options": {"queue": "secretary"},
        },

        # ============ Preference Learning (daily at 03:30) ============
        "consolidate-preferences": {
            "task": "curation.consolidate_preferences",
            "schedule": crontab(hour=3, minute=30),
            "options": {"queue": "secretary"},
        },

        # ============ INSIGHT_IGNORED Detection (every 6 hours) ============
        "check-ignored-insights": {
            "task": "curation.check_ignored_insights",
            "schedule": crontab(hour="*/6", minute=15),
            "options": {"queue": "secretary"},
        },

        # ============ Meal Window Inference (weekly Sunday 03:00) ============
        "weekly-meal-window-inference": {
            "task": "secretary.infer_all_meal_windows",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3:00 AM
            "options": {"queue": "secretary"},
        },

        # ============ Preference Extraction (daily at 05:15) ============
        "extract-preference-rules": {
            "task": "secretary.extract_preference_rules",
            "schedule": crontab(hour=5, minute=15),
            "options": {"queue": "secretary"},
        },

        # ============ Fatigue State Refresh (daily at 05:30) ============
        "refresh-fatigue-state": {
            "task": "secretary.refresh_fatigue_state",
            "schedule": crontab(hour=5, minute=30),
            "options": {"queue": "secretary"},
        },

        # ============ Daily Conversation Summaries (daily at 05:35) ============
        "daily-summaries-generation": {
            "task": "secretary.generate_daily_summaries",
            "schedule": crontab(hour=5, minute=35),
            "options": {"queue": "secretary"},
        },

        # ============ Implicit Feedback (daily at 05:00) ============
        "process-implicit-feedback": {
            "task": "secretary.process_implicit_feedback",
            "schedule": crontab(hour=5, minute=0),
            "options": {"queue": "secretary"},
        },

        # ============ Insight Generation (daily at 06:00) ============
        "generate-daily-insights": {
            "task": "secretary.generate_daily_insights",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "secretary"},
        },

        # ============ Insight Hygiene (daily at 04:00 + every 6h) ============
        "insight-hygiene-cleanup": {
            "task": "secretary.insight_hygiene_cleanup",
            "schedule": crontab(hour="4,10,16,22", minute=0),
            "options": {"queue": "secretary"},
        },

        # ============ Entity Link Repair (daily at 04:45) ============
        "repair-entity-links": {
            "task": "secretary.repair_entity_links",
            "schedule": crontab(hour=4, minute=45),
            "options": {"queue": "secretary"},
        },

        # ============ E8 Placeholder Auto-Expiry (every 2 hours) ============
        "expire-stale-placeholders": {
            "task": "secretary.expire_stale_placeholders",
            "schedule": crontab(hour="*/2", minute=15),
            "options": {"queue": "secretary"},
        },

        # ============ M4 Insight Self-Report (weekly Monday 04:00) ============
        "weekly-insight-self-report": {
            "task": "secretary.generate_insight_self_report",
            "schedule": crontab(hour=4, minute=0, day_of_week=1),  # Monday 04:00 UTC
            "options": {"queue": "secretary"},
        },

        # ============ Four-Wave Insight Delivery ============
        # Insights are generated at 06:00 UTC (generate-daily-insights above).
        # These four tasks deliver already-generated insights to users in waves.
        "secretary-deliver-morning-wave": {
            "task": "secretary.dispatch_wave_delivery",
            "schedule": crontab(hour=7, minute=0),
            "args": ("morning",),
            "options": {"queue": "secretary"},
        },
        "secretary-deliver-noon-wave": {
            "task": "secretary.dispatch_wave_delivery",
            "schedule": crontab(hour=12, minute=0),
            "args": ("noon",),
            "options": {"queue": "secretary"},
        },
        "secretary-deliver-evening-wave": {
            "task": "secretary.dispatch_wave_delivery",
            "schedule": crontab(hour=17, minute=0),
            "args": ("evening",),
            "options": {"queue": "secretary"},
        },
        "secretary-deliver-night-wave": {
            "task": "secretary.dispatch_wave_delivery",
            "schedule": crontab(hour=21, minute=0),
            "args": ("night",),
            "options": {"queue": "secretary"},
        },
    },

    # Task routes
    task_routes={
        "events.*": {"queue": "default"},
        "scheduler.*": {"queue": "default"},
        "reminder.*": {"queue": "default"},
        "gift.*": {"queue": "default"},
        "curation.*": {"queue": "secretary"},
        "secretary.*": {"queue": "secretary"},
        "assistant.*": {"queue": "assistant"},
    },

    # Task default settings
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)


@beat_init.connect
def configure_beat(**kwargs):
    """Configure beat scheduler on startup and trigger backfill."""
    try:
        from .modules.gift.providers import is_promotion_period, get_current_promotion_names

        if is_promotion_period():
            promos = get_current_promotion_names()
            logger.info(f"Starting Celery beat during promotional period: {promos}")
        else:
            logger.info("Starting Celery beat in normal period")
    except ImportError:
        logger.warning("Could not import promotion configuration")

    # Trigger async backfill of Redis sorted sets
    try:
        celery_app.send_task("scheduler.backfill", queue="default")
        logger.info("Triggered scheduler backfill")
    except Exception as e:
        logger.warning("Failed to trigger scheduler backfill: %s", e)


@worker_process_init.connect
def setup_feedback_on_worker(**kwargs):
    """Initialize async runtime and feedback consumers in each worker child."""
    try:
        from .core.scheduler._async_compat import init_worker_event_loop
        from .core.feedback import setup_feedback_consumers
        from .db.session import async_session_maker
        init_worker_event_loop()
        setup_feedback_consumers(async_session_maker)
        logger.info("Initialized async runtime + FeedbackBus in Celery worker")
    except Exception as e:
        logger.warning("Failed to initialize worker async runtime/feedback bus: %s", e)


@worker_process_shutdown.connect
def teardown_async_on_worker(**kwargs):
    """Close process-local async runtime to release loop-bound resources."""
    try:
        from .core.scheduler._async_compat import shutdown_worker_event_loop
        shutdown_worker_event_loop()
    except Exception as e:
        logger.warning("Failed to shutdown worker async runtime cleanly: %s", e)


# Optional: autodiscover tasks from all installed apps
# celery_app.autodiscover_tasks()


if __name__ == "__main__":
    celery_app.start()
