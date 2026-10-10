"""Create secretary memory tables

Revision ID: 035
Revises: 034
Create Date: 2025-01-14

Tables for the intelligent secretary memory system:
- secretary_memories: Long-term memory storage
- secretary_insights: Proactive insights and briefings
- secretary_extraction_logs: Extraction audit trail
- secretary_memory_associations: Memory relationships
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '035_secretary_memory'
down_revision = '034_trending_gift_desc'
branch_labels = None
depends_on = None


def table_exists(connection, table_name):
    """Check if a table exists in the database."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = '{table_name}')"
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Secretary Memories table
    if not table_exists(connection, 'secretary_memories'):
        op.create_table(
            'secretary_memories',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),
            sa.Column('memory_type', sa.String(50), nullable=False),  # emotion, plan, schedule, relationship, preference, task
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('extracted_entities', JSONB),  # Flexible entity storage
            sa.Column('embedding', JSONB),  # Vector embedding for semantic search (future)
            sa.Column('confidence_score', sa.Float, nullable=False, server_default='0.8'),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
            sa.Column('expires_at', sa.DateTime),  # For time-bound memories
            sa.Column('source_conversation_id', UUID(as_uuid=True)),
            sa.Column('source_message', sa.Text),
            sa.Column('created_by', UUID(as_uuid=True)),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_secretary_memories_family_type', 'secretary_memories', ['family_id', 'memory_type'])
        op.create_index('ix_secretary_memories_active', 'secretary_memories', ['family_id', 'is_active'])
        op.create_index('ix_secretary_memories_created', 'secretary_memories', ['created_at'])

    # Secretary Insights table
    if not table_exists(connection, 'secretary_insights'):
        op.create_table(
            'secretary_insights',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),
            sa.Column('insight_type', sa.String(50), nullable=False),  # daily_briefing, reminder, proactive_suggestion, etc.
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # pending, delivered, dismissed
            sa.Column('priority', sa.Integer, nullable=False, server_default='5'),  # 1-10, higher = more important
            sa.Column('trigger_memories', JSONB),  # List of memory IDs that triggered this insight
            sa.Column('context', JSONB),  # Additional context data
            sa.Column('scheduled_at', sa.DateTime),  # When to deliver (null = immediate)
            sa.Column('delivered_at', sa.DateTime),
            sa.Column('dismissed_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_secretary_insights_family_status', 'secretary_insights', ['family_id', 'status'])
        op.create_index('ix_secretary_insights_scheduled', 'secretary_insights', ['scheduled_at', 'status'])
        op.create_index('ix_secretary_insights_type', 'secretary_insights', ['family_id', 'insight_type'])

    # Secretary Extraction Logs table
    if not table_exists(connection, 'secretary_extraction_logs'):
        op.create_table(
            'secretary_extraction_logs',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),
            sa.Column('source_type', sa.String(50), nullable=False),  # conversation, import, manual
            sa.Column('source_message', sa.Text),
            sa.Column('extractor_name', sa.String(100), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),  # pending, completed, failed, skipped
            sa.Column('extracted_type', sa.String(50)),  # Memory type if extraction succeeded
            sa.Column('confidence_score', sa.Float),
            sa.Column('memory_id', UUID(as_uuid=True)),  # Created memory ID if successful
            sa.Column('error_message', sa.Text),
            sa.Column('processing_time_ms', sa.Integer),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_secretary_extraction_logs_family', 'secretary_extraction_logs', ['family_id', 'created_at'])
        op.create_index('ix_secretary_extraction_logs_status', 'secretary_extraction_logs', ['status', 'extractor_name'])

    # Secretary Memory Associations table
    if not table_exists(connection, 'secretary_memory_associations'):
        op.create_table(
            'secretary_memory_associations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),
            sa.Column('source_memory_id', UUID(as_uuid=True), nullable=False),
            sa.Column('target_memory_id', UUID(as_uuid=True), nullable=False),
            sa.Column('association_type', sa.String(50), nullable=False),  # semantic, entity, temporal, causal
            sa.Column('strength', sa.Float, nullable=False, server_default='0.5'),  # 0-1, higher = stronger
            sa.Column('metadata', JSONB),  # Additional association data
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_secretary_associations_source', 'secretary_memory_associations', ['source_memory_id'])
        op.create_index('ix_secretary_associations_target', 'secretary_memory_associations', ['target_memory_id'])
        op.create_index('ix_secretary_associations_family', 'secretary_memory_associations', ['family_id'])

        # Unique constraint to prevent duplicate associations
        op.create_unique_constraint(
            'uq_secretary_associations_pair',
            'secretary_memory_associations',
            ['source_memory_id', 'target_memory_id', 'association_type']
        )


def downgrade():
    op.drop_table('secretary_memory_associations')
    op.drop_table('secretary_extraction_logs')
    op.drop_table('secretary_insights')
    op.drop_table('secretary_memories')
