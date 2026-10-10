"""
Pytest configuration and fixtures for testing.
"""
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.main import app
from src.db.session import Base, get_db
from src.config.settings import settings


# Test database URL (use separate test database)
TEST_DATABASE_URL = settings.database_url.replace("/secretary", "/secretary_test")


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,  # Disable connection pooling for tests
    echo=False
)


# Test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Note: No explicit event_loop fixture needed — asyncio_mode=auto in pytest.ini
# handles event loop lifecycle automatically.


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a test database session with transaction rollback.

    Each test gets a fresh database state.
    """
    # Nuclear reset: drop and recreate public schema for a clean slate.
    # This handles orphaned indexes from coexisting old/new model definitions.
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # Extensions and enum types that create_all doesn't auto-create
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text(
            "CREATE TYPE gender_enum AS ENUM "
            "('male', 'female', 'other', 'unspecified')"
        ))
        await conn.run_sync(Base.metadata.create_all)

    # Create session (no explicit begin — let API routes and unit tests manage
    # their own transactions; per-test isolation is via schema drop/recreate)
    async with TestSessionLocal() as session:
        yield session

    # Clean up after test
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP client for API testing.

    Overrides the get_db dependency to use test database.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_token() -> str:
    """
    Provide a valid JWT token for authenticated requests.

    TODO: Implement actual JWT token generation when auth module is ready.
    """
    # Placeholder: Return a mock token
    return "mock_jwt_token_for_testing"


@pytest.fixture
def test_family_id() -> str:
    """Provide a test family UUID."""
    return "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def test_user_id() -> str:
    """Provide a test user UUID."""
    return "123e4567-e89b-12d3-a456-426614174001"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "contract: Contract tests")
    config.addinivalue_line("markers", "asyncio: Async tests")
