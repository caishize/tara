"""Update secretary_extraction_logs schema to match model

Revision ID: 039_extraction_logs_update
Revises: 038_secretary_memories_update
Create Date: 2026-01-15

Updates secretary_extraction_logs table to match the model.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '039_extraction_logs_update'
down_revision = '038_secretary_memories_update'
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

    # Add source_message_id column
    if not column_exists(connection, 'secretary_extraction_logs', 'source_message_id'):
        op.add_column('secretary_extraction_logs', sa.Column('source_message_id', UUID(as_uuid=True), nullable=True))

    # Add source_session_id column
    if not column_exists(connection, 'secretary_extraction_logs', 'source_session_id'):
        op.add_column('secretary_extraction_logs', sa.Column('source_session_id', UUID(as_uuid=True), nullable=True))

    # Add user_id column
    if not column_exists(connection, 'secretary_extraction_logs', 'user_id'):
        op.add_column('secretary_extraction_logs', sa.Column('user_id', UUID(as_uuid=True), nullable=True))

    # Add message_content column (alias for source_message)
    if not column_exists(connection, 'secretary_extraction_logs', 'message_content'):
        op.add_column('secretary_extraction_logs', sa.Column('message_content', sa.Text, nullable=True))
        # Copy data from source_message
        op.execute("UPDATE secretary_extraction_logs SET message_content = source_message WHERE source_message IS NOT NULL")

    # Add message_role column
    if not column_exists(connection, 'secretary_extraction_logs', 'message_role'):
        op.add_column('secretary_extraction_logs', sa.Column('message_role', sa.String(20), nullable=True, server_default='user'))

    # Add extraction_types column (JSONB)
    if not column_exists(connection, 'secretary_extraction_logs', 'extraction_types'):
        op.add_column('secretary_extraction_logs', sa.Column('extraction_types', JSONB, nullable=True))

    # Add memories_created column
    if not column_exists(connection, 'secretary_extraction_logs', 'memories_created'):
        op.add_column('secretary_extraction_logs', sa.Column('memories_created', sa.Integer, nullable=True, server_default='0'))

    # Add extraction_results column (JSONB)
    if not column_exists(connection, 'secretary_extraction_logs', 'extraction_results'):
        op.add_column('secretary_extraction_logs', sa.Column('extraction_results', JSONB, nullable=True))

    # Add processing_duration_ms column
    if not column_exists(connection, 'secretary_extraction_logs', 'processing_duration_ms'):
        op.add_column('secretary_extraction_logs', sa.Column('processing_duration_ms', sa.Integer, nullable=True))
        # Copy from processing_time_ms if exists
        if column_exists(connection, 'secretary_extraction_logs', 'processing_time_ms'):
            op.execute("UPDATE secretary_extraction_logs SET processing_duration_ms = processing_time_ms")

    # Add llm_tokens_used column
    if not column_exists(connection, 'secretary_extraction_logs', 'llm_tokens_used'):
        op.add_column('secretary_extraction_logs', sa.Column('llm_tokens_used', sa.Integer, nullable=True))

    # Add error_traceback column
    if not column_exists(connection, 'secretary_extraction_logs', 'error_traceback'):
        op.add_column('secretary_extraction_logs', sa.Column('error_traceback', sa.Text, nullable=True))


def downgrade():
    # Drop new columns
    op.drop_column('secretary_extraction_logs', 'error_traceback')
    op.drop_column('secretary_extraction_logs', 'llm_tokens_used')
    op.drop_column('secretary_extraction_logs', 'processing_duration_ms')
    op.drop_column('secretary_extraction_logs', 'extraction_results')
    op.drop_column('secretary_extraction_logs', 'memories_created')
    op.drop_column('secretary_extraction_logs', 'extraction_types')
    op.drop_column('secretary_extraction_logs', 'message_role')
    op.drop_column('secretary_extraction_logs', 'message_content')
    op.drop_column('secretary_extraction_logs', 'user_id')
    op.drop_column('secretary_extraction_logs', 'source_session_id')
    op.drop_column('secretary_extraction_logs', 'source_message_id')
