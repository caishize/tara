"""Add pgvector support for semantic search optimization

Revision ID: 048_pgvector_support
Revises: 047_professional_relations
Create Date: 2026-01-23

Migrates from ARRAY(Float) to pgvector for O(n) -> O(log n) semantic search.
Uses HNSW index for approximate nearest neighbor search.

Note: Requires pgvector extension to be installed on PostgreSQL.
If pgvector is not available, falls back to existing ARRAY(Float) column.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = '048_pgvector_support'
down_revision = '047_professional_relations'
branch_labels = None
depends_on = None


def extension_exists(connection, extension_name):
    """Check if a PostgreSQL extension is available."""
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM pg_available_extensions
                WHERE name = :ext_name
            )
        """),
        {"ext_name": extension_name}
    )
    return result.scalar()


def extension_installed(connection, extension_name):
    """Check if a PostgreSQL extension is installed."""
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM pg_extension
                WHERE extname = :ext_name
            )
        """),
        {"ext_name": extension_name}
    )
    return result.scalar()


def column_exists(connection, table_name, column_name):
    """Check if a column exists in a table."""
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = :table_name
                AND column_name = :column_name
            )
        """),
        {"table_name": table_name, "column_name": column_name}
    )
    return result.scalar()


def index_exists(connection, index_name):
    """Check if an index exists."""
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = :index_name
            )
        """),
        {"index_name": index_name}
    )
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Check if pgvector extension is available and install it
    pgvector_available = extension_exists(connection, 'vector')

    if pgvector_available:
        # Install pgvector extension if not already installed
        if not extension_installed(connection, 'vector'):
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Add embedding_v column with pgvector type (1536 dimensions for OpenAI text-embedding-3-small)
        if not column_exists(connection, 'conversation_memories', 'embedding_v'):
            op.execute("""
                ALTER TABLE conversation_memories
                ADD COLUMN embedding_v vector(1536)
            """)

        # Create HNSW index for fast approximate nearest neighbor search
        # m=16: number of connections per layer (higher = more accurate but slower to build)
        # ef_construction=64: search width during construction (higher = more accurate but slower)
        if not index_exists(connection, 'idx_conv_memories_embedding_hnsw'):
            op.execute("""
                CREATE INDEX idx_conv_memories_embedding_hnsw
                ON conversation_memories
                USING hnsw (embedding_v vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)

        # Migrate existing embeddings from ARRAY(Float) to vector
        # Only migrate non-null embeddings
        op.execute("""
            UPDATE conversation_memories
            SET embedding_v = embedding::vector(1536)
            WHERE embedding IS NOT NULL
            AND embedding_v IS NULL
            AND array_length(embedding, 1) = 1536
        """)

        # Add pgvector columns to memory_summaries table (created in next migration)
        # This will be handled in migration 049

        print("pgvector support enabled successfully")
    else:
        print("WARNING: pgvector extension not available. Falling back to ARRAY(Float) for embeddings.")
        print("To enable pgvector, install it: CREATE EXTENSION vector;")


def downgrade():
    connection = op.get_bind()

    # Check if pgvector is installed
    if extension_installed(connection, 'vector'):
        # Drop HNSW index
        if index_exists(connection, 'idx_conv_memories_embedding_hnsw'):
            op.execute("DROP INDEX IF EXISTS idx_conv_memories_embedding_hnsw")

        # Migrate data back from vector to ARRAY (optional - for safety)
        op.execute("""
            UPDATE conversation_memories
            SET embedding = embedding_v::float[]
            WHERE embedding_v IS NOT NULL
            AND embedding IS NULL
        """)

        # Drop embedding_v column
        if column_exists(connection, 'conversation_memories', 'embedding_v'):
            op.drop_column('conversation_memories', 'embedding_v')

        # Note: We don't drop the pgvector extension as other tables might use it
