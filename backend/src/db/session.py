"""
Database session management.
Provides async SQLAlchemy engine and session factory.
"""
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import AsyncGenerator, Tuple

from ..config.settings import settings


# SQLAlchemy Base for models
Base = declarative_base()


# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to False to suppress SQL logs; use logging config for control
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Verify connections before using
    connect_args=settings.database_connect_args,
)


# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Alias for background task usage
async_session_maker = AsyncSessionLocal


def _get_sync_database_url() -> str:
    """Convert async database URL to sync format for Celery tasks."""
    url = settings.database_url
    # postgresql+asyncpg:// -> postgresql://
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "")
    # postgresql+aiosqlite:// -> sqlite://
    if "+aiosqlite" in url:
        return url.replace("+aiosqlite", "")
    return url


# Sync engine for Celery tasks
_sync_engine = create_engine(
    _get_sync_database_url(),
    echo=False,  # Set to False to suppress SQL logs; use logging config for control
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)

# Sync session factory for Celery tasks
SessionLocal = sessionmaker(
    bind=_sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get database session.

    Usage:
        @app.get("/members")
        async def get_members(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database (create all tables)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator for getting database sessions.
    Used by background tasks and scheduled jobs.

    Usage:
        async for session in get_async_session():
            # use session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager version of get_async_session.
    Used by services that need direct session access via `async with`.

    Usage:
        async with get_db_session() as session:
            # use session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def create_celery_async_session() -> Tuple[AsyncEngine, async_sessionmaker]:
    """
    Create a fresh async engine and session factory for Celery tasks.

    This function creates new engine/session instances that are bound to the
    current event loop, avoiding the "Future attached to a different loop" error
    that occurs when using the module-level engine in Celery workers.

    Usage in Celery tasks:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            engine, session_factory = create_celery_async_session()
            async with session_factory() as session:
                # use session
            await engine.dispose()
        finally:
            loop.close()

    Returns:
        Tuple of (AsyncEngine, async_sessionmaker)
    """
    celery_engine = create_async_engine(
        settings.database_url,
        echo=False,  # Set to False to suppress SQL logs; use logging config for control
        pool_size=5,  # Smaller pool for Celery workers
        max_overflow=2,
        pool_pre_ping=True,
        connect_args=settings.database_connect_args,
    )

    celery_session_factory = async_sessionmaker(
        celery_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    return celery_engine, celery_session_factory
