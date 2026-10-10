"""Update secretary insights schema to match model

Revision ID: 037_update_secretary_insights
Revises: 036_add_itinerary_versions
Create Date: 2026-01-15

Updates secretary_insights table to match the model:
- Add user_id column
- Add action_suggestions column
- Rename trigger_memories to related_memory_ids
- Rename context to trigger_context
- Rename scheduled_at to scheduled_delivery_at
- Add trigger_rule column
- Add acted_at column
- Add expires_at column
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '037_update_secretary_insights'
down_revision = '036_add_itinerary_versions'
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
    if not column_exists(connection, 'secretary_insights', 'user_id'):
        op.add_column('secretary_insights', sa.Column('user_id', UUID(as_uuid=True), nullable=True))

    # Add action_suggestions column if not exists
    if not column_exists(connection, 'secretary_insights', 'action_suggestions'):
        op.add_column('secretary_insights', sa.Column('action_suggestions', JSONB, nullable=True))

    # Add trigger_rule column if not exists
    if not column_exists(connection, 'secretary_insights', 'trigger_rule'):
        op.add_column('secretary_insights', sa.Column('trigger_rule', sa.String(100), nullable=True))

    # Add acted_at column if not exists
    if not column_exists(connection, 'secretary_insights', 'acted_at'):
        op.add_column('secretary_insights', sa.Column('acted_at', sa.DateTime, nullable=True))

    # Add expires_at column if not exists
    if not column_exists(connection, 'secretary_insights', 'expires_at'):
        op.add_column('secretary_insights', sa.Column('expires_at', sa.DateTime, nullable=True))

    # Rename trigger_memories to related_memory_ids if needed
    if column_exists(connection, 'secretary_insights', 'trigger_memories') and not column_exists(connection, 'secretary_insights', 'related_memory_ids'):
        op.alter_column('secretary_insights', 'trigger_memories', new_column_name='related_memory_ids')
    elif not column_exists(connection, 'secretary_insights', 'related_memory_ids'):
        op.add_column('secretary_insights', sa.Column('related_memory_ids', JSONB, nullable=True))

    # Rename context to trigger_context if needed
    if column_exists(connection, 'secretary_insights', 'context') and not column_exists(connection, 'secretary_insights', 'trigger_context'):
        op.alter_column('secretary_insights', 'context', new_column_name='trigger_context')
    elif not column_exists(connection, 'secretary_insights', 'trigger_context'):
        op.add_column('secretary_insights', sa.Column('trigger_context', JSONB, nullable=True))

    # Rename scheduled_at to scheduled_delivery_at if needed
    if column_exists(connection, 'secretary_insights', 'scheduled_at') and not column_exists(connection, 'secretary_insights', 'scheduled_delivery_at'):
        op.alter_column('secretary_insights', 'scheduled_at', new_column_name='scheduled_delivery_at')
    elif not column_exists(connection, 'secretary_insights', 'scheduled_delivery_at'):
        op.add_column('secretary_insights', sa.Column('scheduled_delivery_at', sa.DateTime, nullable=True))


def downgrade():
    # Rename back
    op.alter_column('secretary_insights', 'related_memory_ids', new_column_name='trigger_memories')
    op.alter_column('secretary_insights', 'trigger_context', new_column_name='context')
    op.alter_column('secretary_insights', 'scheduled_delivery_at', new_column_name='scheduled_at')

    # Drop new columns
    op.drop_column('secretary_insights', 'expires_at')
    op.drop_column('secretary_insights', 'acted_at')
    op.drop_column('secretary_insights', 'trigger_rule')
    op.drop_column('secretary_insights', 'action_suggestions')
    op.drop_column('secretary_insights', 'user_id')
