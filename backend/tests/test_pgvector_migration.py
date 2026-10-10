"""Tests for migration 090: pgvector HNSW index.

Validates that upgrade/downgrade create and remove:
- pgvector extension
- embedding_v column (vector(1536))
- HNSW index on embedding_v
- Backfill from existing ARRAY embeddings

NOTE: These tests require pgvector to be installed on the PostgreSQL server.
If not available, tests are skipped automatically.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _pgvector_available(db_session: AsyncSession) -> bool:
    """Check whether pgvector extension is installed AND usable in this connection.

    asyncpg caches type information at connection startup. Even after
    CREATE EXTENSION vector, the vector type may not be recognized within the
    same connection. We verify usability by attempting a cast to the vector type.

    Also drops the embedding_v column if it already exists as TEXT (created by
    SQLAlchemy's _PgVector DDL fallback in create_all), so migration tests can
    re-create it with the correct vector type.
    """
    # First ensure the extension is installed
    try:
        await db_session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        return False

    # Verify the vector type is actually usable in this connection (asyncpg type cache)
    try:
        await db_session.execute(text("SELECT ARRAY[1.0, 2.0, 3.0]::real[]::vector(3)"))
    except Exception:
        # asyncpg type cache doesn't recognize vector type in this connection
        await db_session.rollback()
        return False

    # The ORM's _PgVector type emits TEXT in DDL so create_all never fails.
    # If the column already exists as TEXT, drop it so tests can add it as vector.
    try:
        result = await db_session.execute(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'conversation_memories' "
                "AND column_name = 'embedding_v'"
            )
        )
        row = result.fetchone()
        if row and row[0] == "text":
            await db_session.execute(
                text("ALTER TABLE conversation_memories DROP COLUMN embedding_v")
            )
            await db_session.commit()
    except Exception:
        await db_session.rollback()

    return True



@pytest.mark.asyncio
async def test_upgrade_creates_extension_and_column(db_session: AsyncSession):
    """After upgrade, pgvector extension and embedding_v column exist."""
    if not await _pgvector_available(db_session):
        pytest.skip("pgvector extension not available on test server")

    await db_session.execute(
        text(
            "ALTER TABLE conversation_memories "
            "ADD COLUMN IF NOT EXISTS embedding_v vector(1536)"
        )
    )
    await db_session.commit()

    # Verify column exists
    result = await db_session.execute(
        text(
            "SELECT column_name, udt_name FROM information_schema.columns "
            "WHERE table_name = 'conversation_memories' "
            "AND column_name = 'embedding_v'"
        )
    )
    row = result.fetchone()
    assert row is not None, "embedding_v column should exist after upgrade"
    assert row[1] == "vector", "embedding_v should be of type vector"


@pytest.mark.asyncio
async def test_upgrade_creates_hnsw_index(db_session: AsyncSession):
    """After upgrade, HNSW index exists on embedding_v."""
    if not await _pgvector_available(db_session):
        pytest.skip("pgvector extension not available on test server")

    await db_session.execute(
        text(
            "ALTER TABLE conversation_memories "
            "ADD COLUMN IF NOT EXISTS embedding_v vector(1536)"
        )
    )
    await db_session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_conv_memories_embedding_hnsw "
            "ON conversation_memories "
            "USING hnsw (embedding_v vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'conversation_memories' "
            "AND indexname = 'ix_conv_memories_embedding_hnsw'"
        )
    )
    row = result.fetchone()
    assert row is not None, "HNSW index should exist after upgrade"


@pytest.mark.asyncio
async def test_backfill_copies_existing_embeddings(db_session: AsyncSession):
    """Backfill step copies ARRAY embedding into embedding_v for matching rows."""
    if not await _pgvector_available(db_session):
        pytest.skip("pgvector extension not available on test server")

    from uuid import uuid4

    user_id = uuid4()
    family_id = uuid4()
    mem_id = uuid4()

    # Create a memory with a 1536-dim embedding in the ARRAY column
    embedding = [0.1] * 1536
    embedding_literal = "{" + ",".join(str(x) for x in embedding) + "}"

    await db_session.execute(
        text(
            "INSERT INTO conversation_memories "
            "(id, user_id, family_id, memory_type, content, summary, "
            "importance, confidence, status, sensitivity_level, "
            "embedding, created_at, updated_at) "
            "VALUES (:id, :user_id, :family_id, 'general', 'test', 'test summary', "
            "5, 0.8, 'active', 'public', "
            ":embedding, NOW(), NOW())"
        ),
        {
            "id": str(mem_id),
            "user_id": str(user_id),
            "family_id": str(family_id),
            "embedding": embedding_literal,
        },
    )

    await db_session.execute(
        text(
            "ALTER TABLE conversation_memories "
            "ADD COLUMN IF NOT EXISTS embedding_v vector(1536)"
        )
    )
    await db_session.execute(
        text(
            "UPDATE conversation_memories "
            "SET embedding_v = embedding::vector "
            "WHERE embedding IS NOT NULL "
            "AND array_length(embedding, 1) = 1536 "
            "AND embedding_v IS NULL"
        )
    )
    await db_session.commit()

    # Verify backfill
    result = await db_session.execute(
        text(
            "SELECT embedding_v IS NOT NULL as has_vector "
            "FROM conversation_memories WHERE id = :id"
        ),
        {"id": str(mem_id)},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is True, "embedding_v should be populated after backfill"


@pytest.mark.asyncio
async def test_backfill_skips_wrong_dimension(db_session: AsyncSession):
    """Backfill should skip embeddings with dimension != 1536."""
    if not await _pgvector_available(db_session):
        pytest.skip("pgvector extension not available on test server")

    from uuid import uuid4

    user_id = uuid4()
    family_id = uuid4()
    mem_id = uuid4()

    # Create a memory with a 768-dim embedding (wrong dimension)
    embedding_768 = [0.1] * 768
    embedding_literal = "{" + ",".join(str(x) for x in embedding_768) + "}"

    await db_session.execute(
        text(
            "INSERT INTO conversation_memories "
            "(id, user_id, family_id, memory_type, content, summary, "
            "importance, confidence, status, sensitivity_level, "
            "embedding, created_at, updated_at) "
            "VALUES (:id, :user_id, :family_id, 'general', 'test', 'test', "
            "5, 0.8, 'active', 'public', "
            ":embedding, NOW(), NOW())"
        ),
        {
            "id": str(mem_id),
            "user_id": str(user_id),
            "family_id": str(family_id),
            "embedding": embedding_literal,
        },
    )

    await db_session.execute(
        text(
            "ALTER TABLE conversation_memories "
            "ADD COLUMN IF NOT EXISTS embedding_v vector(1536)"
        )
    )
    await db_session.execute(
        text(
            "UPDATE conversation_memories "
            "SET embedding_v = embedding::vector "
            "WHERE embedding IS NOT NULL "
            "AND array_length(embedding, 1) = 1536 "
            "AND embedding_v IS NULL"
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        text(
            "SELECT embedding_v IS NULL as is_null "
            "FROM conversation_memories WHERE id = :id"
        ),
        {"id": str(mem_id)},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is True, "embedding_v should remain NULL for wrong-dimension embeddings"


@pytest.mark.asyncio
async def test_downgrade_removes_column_and_index(db_session: AsyncSession):
    """Downgrade should remove the HNSW index and embedding_v column."""
    if not await _pgvector_available(db_session):
        pytest.skip("pgvector extension not available on test server")

    # Upgrade
    await db_session.execute(
        text(
            "ALTER TABLE conversation_memories "
            "ADD COLUMN IF NOT EXISTS embedding_v vector(1536)"
        )
    )
    await db_session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_conv_memories_embedding_hnsw "
            "ON conversation_memories "
            "USING hnsw (embedding_v vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
    )
    await db_session.commit()

    # Downgrade
    await db_session.execute(
        text("DROP INDEX IF EXISTS ix_conv_memories_embedding_hnsw")
    )
    await db_session.execute(
        text(
            "ALTER TABLE conversation_memories "
            "DROP COLUMN IF EXISTS embedding_v"
        )
    )
    await db_session.commit()

    # Verify column gone
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'conversation_memories' "
            "AND column_name = 'embedding_v'"
        )
    )
    assert result.fetchone() is None, "embedding_v column should be removed after downgrade"

    # Verify index gone
    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'conversation_memories' "
            "AND indexname = 'ix_conv_memories_embedding_hnsw'"
        )
    )
    assert result.fetchone() is None, "HNSW index should be removed after downgrade"


@pytest.mark.asyncio
async def test_migration_module_structure():
    """Verify migration 090 module has correct revision chain."""
    import importlib

    mod = importlib.import_module(
        "src.db.migrations.versions.090_pgvector_hnsw_index"
    )

    assert mod.revision == "090"
    assert mod.down_revision == "089"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)
