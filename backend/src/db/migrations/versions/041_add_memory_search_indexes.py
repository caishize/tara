"""Add performance indexes for memory search

Revision ID: 041_memory_search_indexes
Revises: 040_conversation_memory
Create Date: 2026-01-18

Adds optimized indexes for memory search operations:
- Full-text search on summary field
- Functional indexes on frequently queried JSONB fields
- Composite index for insight deduplication
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '041_memory_search_indexes'
down_revision = '040_conversation_memory'
branch_labels = None
depends_on = None


def index_exists(connection, index_name):
    """Check if an index exists in the database."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}')"
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Full-text search index on summary for efficient text search
    if not index_exists(connection, 'ix_conv_memories_summary_fts'):
        op.execute("""
            CREATE INDEX ix_conv_memories_summary_fts
            ON conversation_memories
            USING gin (to_tsvector('simple', summary))
        """)

    # Functional index for location search (case-insensitive)
    if not index_exists(connection, 'ix_conv_memories_location'):
        op.execute("""
            CREATE INDEX ix_conv_memories_location
            ON conversation_memories
            USING gin (to_tsvector('simple', COALESCE(entities->>'location', '')))
        """)

    # Functional index for person search (case-insensitive)
    if not index_exists(connection, 'ix_conv_memories_person'):
        op.execute("""
            CREATE INDEX ix_conv_memories_person
            ON conversation_memories
            USING gin (to_tsvector('simple', COALESCE(entities->>'person', '')))
        """)

    # Composite index for common memory queries (user + status + importance)
    if not index_exists(connection, 'ix_conv_memories_user_active_important'):
        op.create_index(
            'ix_conv_memories_user_active_important',
            'conversation_memories',
            ['user_id', 'status', 'importance'],
            postgresql_where=sa.text("status = 'active'")
        )

    # Index for expiration cleanup
    if not index_exists(connection, 'ix_conv_memories_expires'):
        op.create_index(
            'ix_conv_memories_expires',
            'conversation_memories',
            ['expires_at'],
            postgresql_where=sa.text("expires_at IS NOT NULL")
        )

    # Insight deduplication index (user + type + date)
    if not index_exists(connection, 'ix_memory_insights_user_type_date'):
        op.execute("""
            CREATE INDEX ix_memory_insights_user_type_date
            ON memory_insights (user_id, insight_type, DATE(created_at))
        """)

    # Index for insight expiration
    if not index_exists(connection, 'ix_memory_insights_expires'):
        op.create_index(
            'ix_memory_insights_expires',
            'memory_insights',
            ['expires_at'],
            postgresql_where=sa.text("expires_at IS NOT NULL AND status = 'pending'")
        )


def downgrade():
    # Drop indexes in reverse order
    op.execute("DROP INDEX IF EXISTS ix_memory_insights_expires")
    op.execute("DROP INDEX IF EXISTS ix_memory_insights_user_type_date")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_expires")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_user_active_important")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_person")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_location")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_summary_fts")
