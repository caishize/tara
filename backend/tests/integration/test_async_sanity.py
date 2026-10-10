"""Async fixture sanity test with DB."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import test_engine, TestSessionLocal, Base


@pytest.fixture
async def test_db() -> AsyncSession:
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
        async with session.begin():
            yield session
            await session.rollback()
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


async def test_db_session_works(test_db):
    assert test_db is not None
