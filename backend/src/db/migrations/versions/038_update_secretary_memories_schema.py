"""Update secretary_memories schema to match model

Revision ID: 038_secretary_memories_update
Revises: 037_update_secretary_insights
Create Date: 2026-01-15

Updates secretary_memories table to match the model:
- Add user_id column (alias for created_by)
- Add original_context column (alias for source_message)
- Add source_message_id column
- Rename source_conversation_id to source_session_id
- Add relevance_score column
- Add resolved_at column
- Add mentioned_at column
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '038_secretary_memories_update'
down_revision = '037_update_secretary_insights'
branch_labels = None
depends_on = None


def column_exists(connection, table_name, column_name):
    """Check if a column exists in a table."""
    result = connection.execute(sa.text(
        f"""SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = '{table_name}'
            AND column_name = '{column_name}'
        )"""
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Add user_id column if not exists
    if not column_exists(connection, 'secretary_memories', 'user_id'):
        op.add_column('secretary_memories', sa.Column('user_id', UUID(as_uuid=True), nullable=True))
        # Copy data from created_by to user_id
        op.execute("UPDATE secretary_memories SET user_id = created_by WHERE created_by IS NOT NULL")

    # Add original_context column if not exists
    if not column_exists(connection, 'secretary_memories', 'original_context'):
        op.add_column('secretary_memories', sa.Column('original_context', sa.Text, nullable=True))
        # Copy data from source_message to original_context
        op.execute("UPDATE secretary_memories SET original_context = source_message WHERE source_message IS NOT NULL")
        # Set default for original_context
        op.execute("UPDATE secretary_memories SET original_context = '' WHERE original_context IS NULL")

    # Add source_message_id column if not exists
    if not column_exists(connection, 'secretary_memories', 'source_message_id'):
        op.add_column('secretary_memories', sa.Column('source_message_id', UUID(as_uuid=True), nullable=True))

    # Rename source_conversation_id to source_session_id if needed
    if column_exists(connection, 'secretary_memories', 'source_conversation_id') and not column_exists(connection, 'secretary_memories', 'source_session_id'):
        op.alter_column('secretary_memories', 'source_conversation_id', new_column_name='source_session_id')
    elif not column_exists(connection, 'secretary_memories', 'source_session_id'):
        op.add_column('secretary_memories', sa.Column('source_session_id', UUID(as_uuid=True), nullable=True))

    # Add relevance_score column if not exists
    if not column_exists(connection, 'secretary_memories', 'relevance_score'):
        op.add_column('secretary_memories', sa.Column('relevance_score', sa.Float, nullable=True))

    # Add resolved_at column if not exists
    if not column_exists(connection, 'secretary_memories', 'resolved_at'):
        op.add_column('secretary_memories', sa.Column('resolved_at', sa.DateTime, nullable=True))

    # Add mentioned_at column if not exists
    if not column_exists(connection, 'secretary_memories', 'mentioned_at'):
        op.add_column('secretary_memories', sa.Column('mentioned_at', sa.DateTime, nullable=True))
        # Set default value to created_at
        op.execute("UPDATE secretary_memories SET mentioned_at = created_at WHERE mentioned_at IS NULL")

    # Create indexes if they don't exist
    try:
        op.create_index('idx_secretary_memory_user_type', 'secretary_memories', ['user_id', 'memory_type'])
    except Exception:
        pass  # Index might already exist

    try:
        op.create_index('idx_secretary_memory_mentioned', 'secretary_memories', ['mentioned_at'])
    except Exception:
        pass


def downgrade():
    # Drop new columns
    op.drop_column('secretary_memories', 'mentioned_at')
    op.drop_column('secretary_memories', 'resolved_at')
    op.drop_column('secretary_memories', 'relevance_score')

    # Rename source_session_id back
    op.alter_column('secretary_memories', 'source_session_id', new_column_name='source_conversation_id')

    op.drop_column('secretary_memories', 'source_message_id')
    op.drop_column('secretary_memories', 'original_context')
    op.drop_column('secretary_memories', 'user_id')
