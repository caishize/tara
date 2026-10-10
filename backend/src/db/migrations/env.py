"""
Alembic migration environment.
"""
from logging.config import fileConfig
import asyncio

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import the Base metadata and all models
# NOTE: Must use absolute imports here — Alembic loads env.py as a standalone
# module (not as part of a package), so relative imports will fail.
from src.db.session import Base
from src.config.settings import settings

# Import ALL models so Alembic autogenerate can detect every table.
# Total: 65 model classes across 12 modules + core
#
# NOTE: Must use absolute imports — Alembic loads env.py standalone.

# ── Member models (11) ────────────────────────────────────────────
from src.modules.member.models.user import User  # noqa: F401
from src.modules.member.models.member import Member, MemberProfile, MemberRelation  # noqa: F401
from src.modules.member.models.family import Family  # noqa: F401
from src.modules.member.models.device_token import DeviceToken  # noqa: F401
from src.modules.member.models.person_profile import PersonProfile  # noqa: F401
from src.modules.member.models.relationship import RelationshipEdge, ProactiveInsight  # noqa: F401
from src.modules.member.models.professional import ProfessionalRelation, WorkHistory  # noqa: F401

# ── Trip models (5) ───────────────────────────────────────────────
from src.modules.trip.models.trip_plan import TripPlan  # noqa: F401
from src.modules.trip.models.trip_itinerary import TripItinerary  # noqa: F401
from src.modules.trip.models.trip_expense import TripExpense  # noqa: F401
from src.modules.trip.models.trip_memory import TripMemory  # noqa: F401
from src.modules.trip.models.itinerary_version import ItineraryVersion  # noqa: F401

# ── Conversation models (5) ──────────────────────────────────────
from src.modules.conversation.models import (  # noqa: F401
    AssistantChatSession,
    ConversationMessage,
    SessionSummary,
    ToolExecutionLog,
)
from src.modules.conversation.pending_action import PendingAction  # noqa: F401

# ── Memory models (4) ────────────────────────────────────────────
from src.modules.memory.models import (  # noqa: F401
    ConversationMemory,
    MemoryAssociation,
    MemorySummary,
)
from src.modules.memory.secretary_note_model import SecretaryNote  # noqa: F401

# ── Insight models (3) ───────────────────────────────────────────
from src.modules.insight.models import MemoryInsight, InsightFeedback  # noqa: F401
from src.modules.insight.insight_settings_model import UserInsightSettings  # noqa: F401

# ── Curation models (6) ──────────────────────────────────────────
from src.modules.curation.models import (  # noqa: F401
    CuratedEvent,
    EventAssociation,
    CurationJob,
    HygieneRunLog,
    PreparationItem,
    SocialIntent,
)

# ── Views models (3) ─────────────────────────────────────────────
from src.modules.views.models import FamilyTask, TodayItem, AISuggestion  # noqa: F401

# ── Briefing models (4) ──────────────────────────────────────────
from src.modules.briefing.models import (  # noqa: F401
    UserInsight,
    UserBriefingSettings,
    PreparationPlan,
    PreparationTask,
)

# ── Date Manager models (7) ──────────────────────────────────────
from src.modules.date_manager.date_models import (  # noqa: F401
    ImportantDate,
    DateReminder,
    DateOccurrence,
)
from src.modules.date_manager.reminder_models import (  # noqa: F401
    EventReminder,
    SmartReminder,
    UserActivityPattern,
)
from src.modules.date_manager.holiday_models import ChineseHolidayPlan  # noqa: F401

# ── Relationship models (2) ──────────────────────────────────────
from src.modules.relationship.models import FavorRecord, SocialEvent  # noqa: F401

# ── Gift models (12) ─────────────────────────────────────────────
from src.modules.gift.models_recommendation import (  # noqa: F401
    GiftRecommendation,
    GiftTask,
    GiftPreference,
    GiftHistory,
    GiftConversationContext,
    MemberGiftMemory,
)
from src.modules.gift.models_trending import (  # noqa: F401
    TrendingGift,
    Occasion,
    OccasionGift,
    DataSource,
    UpdateLog,
    UserGiftSave,
)

# ── Core models (3) ──────────────────────────────────────────────
from src.core.events.outbox import OutboxEvent  # noqa: F401
from src.core.scheduler.job_execution import JobExecutionModel, SchedulerConfigModel  # noqa: F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from settings
# Keep asyncpg for async migrations
config.set_main_option("sqlalchemy.url", settings.database_url)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async support."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
