"""Add trigger conditions to conversation memories

Revision ID: 044_memory_trigger_conditions
Revises: 043_data_connection_tables
Create Date: 2026-01-21

Adds trigger condition fields to conversation_memories table:
- trigger_conditions: JSONB for storing trigger rules
- trigger_count: How many times the trigger has fired
- last_triggered_at: When the trigger last fired

This enables "conditional memory" features like:
- "When I mention Beijing, remind me to contact Li Siyuan"
- "When a trip is approaching, surface related plans"
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '044_memory_trigger_conditions'
down_revision = '043_data_connection'
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

    # Add trigger_conditions column
    if not column_exists(connection, 'conversation_memories', 'trigger_conditions'):
        op.add_column(
            'conversation_memories',
            sa.Column('trigger_conditions', JSONB, server_default='{}', nullable=True)
        )

    # Add trigger_count column
    if not column_exists(connection, 'conversation_memories', 'trigger_count'):
        op.add_column(
            'conversation_memories',
            sa.Column('trigger_count', sa.Integer, server_default='0', nullable=False)
        )

    # Add last_triggered_at column
    if not column_exists(connection, 'conversation_memories', 'last_triggered_at'):
        op.add_column(
            'conversation_memories',
            sa.Column('last_triggered_at', sa.DateTime, nullable=True)
        )

    # Create index for efficient trigger condition queries
    # This allows fast lookup of memories that have triggers set
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_conv_memories_has_trigger
        ON conversation_memories ((trigger_conditions IS NOT NULL AND trigger_conditions != '{}'))
        WHERE trigger_conditions IS NOT NULL AND trigger_conditions != '{}'
    """)

    # Create GIN index on trigger_conditions for JSONB queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_conv_memories_trigger_conditions
        ON conversation_memories USING gin (trigger_conditions)
        WHERE trigger_conditions IS NOT NULL AND trigger_conditions != '{}'
    """)


def downgrade():
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_has_trigger")
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_trigger_conditions")

    # Drop columns
    op.drop_column('conversation_memories', 'last_triggered_at')
    op.drop_column('conversation_memories', 'trigger_count')
    op.drop_column('conversation_memories', 'trigger_conditions')
