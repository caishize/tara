"""Add embedding and feedback fields to conversation memories

Revision ID: 045_embedding_feedback
Revises: 044_memory_trigger_conditions
Create Date: 2026-01-21

Adds:
- embedding: ARRAY(Float) for semantic search
- feedback_weight: Float for user feedback learning
- dismiss_count: Integer for tracking dismissals
- useful_count: Integer for tracking positive feedback
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = '045_embedding_feedback'
down_revision = '044_memory_trigger_conditions'
branch_labels = None
depends_on = None


def column_exists(connection, table_name, column_name):
    """Check if a column exists in a table."""
    result = connection.execute(sa.text(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = '{table_name}'
            AND column_name = '{column_name}'
        )
    """))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Add embedding column for semantic search
    if not column_exists(connection, 'conversation_memories', 'embedding'):
        op.add_column(
            'conversation_memories',
            sa.Column('embedding', ARRAY(sa.Float), nullable=True)
        )

    # Add feedback_weight column for user feedback learning
    if not column_exists(connection, 'conversation_memories', 'feedback_weight'):
        op.add_column(
            'conversation_memories',
            sa.Column('feedback_weight', sa.Float, server_default='1.0', nullable=False)
        )

    # Add dismiss_count column
    if not column_exists(connection, 'conversation_memories', 'dismiss_count'):
        op.add_column(
            'conversation_memories',
            sa.Column('dismiss_count', sa.Integer, server_default='0', nullable=False)
        )

    # Add useful_count column
    if not column_exists(connection, 'conversation_memories', 'useful_count'):
        op.add_column(
            'conversation_memories',
            sa.Column('useful_count', sa.Integer, server_default='0', nullable=False)
        )

    # Create partial index for memories with embeddings (for faster semantic search)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_conv_memories_has_embedding
        ON conversation_memories ((embedding IS NOT NULL))
        WHERE embedding IS NOT NULL
    """)

    # Create index for feedback_weight to optimize weighted sorting
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_conv_memories_feedback_weight
        ON conversation_memories (feedback_weight DESC)
        WHERE status = 'active'
    """)


def downgrade():
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_has_embedding")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_feedback_weight")

    # Drop columns
    op.drop_column('conversation_memories', 'useful_count')
    op.drop_column('conversation_memories', 'dismiss_count')
    op.drop_column('conversation_memories', 'feedback_weight')
    op.drop_column('conversation_memories', 'embedding')
