"""
Pytest configuration and fixtures for secretary module tests.
"""
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from uuid import uuid4

from src.config.settings import settings
from src.db.session import Base

# Import all models so they register with Base.metadata before create_all
import src.main  # noqa: F401


# Test database URL (use separate test database)
TEST_DATABASE_URL = settings.database_url.replace("/secretary", "/secretary_test")


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)


# Test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a test database session with a full schema (all tables created).
    Each test gets a fresh database state via schema drop/recreate.
    """
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text(
            "CREATE TYPE gender_enum AS ENUM "
            "('male', 'female', 'other', 'unspecified')"
        ))
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="function")
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for db_session to support tests that use async_session parameter."""
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text(
            "CREATE TYPE gender_enum AS ENUM "
            "('male', 'female', 'other', 'unspecified')"
        ))
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def test_family_id() -> uuid4:
    """Provide a test family UUID."""
    return uuid4()


@pytest.fixture
def test_user_id() -> uuid4:
    """Provide a test user UUID."""
    return uuid4()
