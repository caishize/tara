"""Add pgvector embedding_v column and HNSW index to conversation_memories.

The existing ``embedding`` column (ARRAY(Float)) is kept for backward
compatibility.  A new ``embedding_v`` column of type ``vector(1536)`` is
added so that pgvector operators (cosine distance ``<=>``) and HNSW
indexing can be used for O(log n) similarity search.

Backfill: existing non-NULL ``embedding`` arrays are copied into the
new ``embedding_v`` column.

Revision ID: 090
Revises: 089
"""

from alembic import op
import sqlalchemy as sa


revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Add the pgvector column (1536 dimensions = OpenAI text-embedding-3-small)
    op.execute(
        "ALTER TABLE conversation_memories "
        "ADD COLUMN IF NOT EXISTS embedding_v vector(1536)"
    )

    # 3. Backfill: copy existing ARRAY embeddings into the new vector column.
    #    Only rows with a non-NULL embedding whose length is exactly 1536 are
    #    eligible; mismatched lengths are left NULL so they can be re-embedded.
    op.execute(
        "UPDATE conversation_memories "
        "SET embedding_v = embedding::vector "
        "WHERE embedding IS NOT NULL "
        "AND array_length(embedding, 1) = 1536 "
        "AND embedding_v IS NULL"
    )

    # 4. Create HNSW index for fast cosine similarity lookups.
    #    m=16 and ef_construction=64 are sensible defaults for datasets
    #    up to a few million rows.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conv_memories_embedding_hnsw "
        "ON conversation_memories "
        "USING hnsw (embedding_v vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_embedding_hnsw")
    op.execute(
        "ALTER TABLE conversation_memories "
        "DROP COLUMN IF EXISTS embedding_v"
    )
