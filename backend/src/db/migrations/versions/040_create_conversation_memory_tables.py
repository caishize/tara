"""Create conversation memory tables

Revision ID: 040_conversation_memory
Revises: 039_extraction_logs_update
Create Date: 2026-01-18

Creates the conversation memory system tables:
- conversation_memories: Stores extracted memories from conversations
- memory_insights: AI-generated insights based on memories
- memory_associations: Links between related memories
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = '040_conversation_memory'
down_revision = '039_extraction_logs_update'
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

    # Conversation Memories table
    if not table_exists(connection, 'conversation_memories'):
        op.create_table(
            'conversation_memories',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),

            # Memory content
            sa.Column('memory_type', sa.String(30), nullable=False),
            sa.Column('content', sa.Text, nullable=False),  # Original text
            sa.Column('summary', sa.Text, nullable=False),  # LLM-generated summary

            # Extracted entities (structured data)
            sa.Column('entities', JSONB, server_default='{}'),

            # Tags for quick filtering
            sa.Column('tags', ARRAY(sa.String), server_default='{}'),

            # Importance and confidence
            sa.Column('importance', sa.Integer, nullable=False, server_default='5'),
            sa.Column('confidence', sa.Float, nullable=False, server_default='0.8'),

            # Status and lifecycle
            sa.Column('status', sa.String(20), nullable=False, server_default='active'),
            sa.Column('expires_at', sa.DateTime, nullable=True),

            # Source tracking
            sa.Column('source_session_id', UUID(as_uuid=True), nullable=True),
            sa.Column('source_message_id', UUID(as_uuid=True), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('last_recalled_at', sa.DateTime, nullable=True),
            sa.Column('recall_count', sa.Integer, nullable=False, server_default='0'),
        )

        # Create indexes
        op.create_index('ix_conv_memories_user_id', 'conversation_memories', ['user_id'])
        op.create_index('ix_conv_memories_family_id', 'conversation_memories', ['family_id'])
        op.create_index('ix_conv_memories_memory_type', 'conversation_memories', ['memory_type'])
        op.create_index('ix_conv_memories_status', 'conversation_memories', ['status'])
        op.create_index('ix_conv_memories_user_type', 'conversation_memories', ['user_id', 'memory_type'])
        op.create_index('ix_conv_memories_user_status', 'conversation_memories', ['user_id', 'status'])
        op.create_index('ix_conv_memories_family_type', 'conversation_memories', ['family_id', 'memory_type'])
        op.create_index('ix_conv_memories_created', 'conversation_memories', ['created_at'])
        op.create_index('ix_conv_memories_tags', 'conversation_memories', ['tags'], postgresql_using='gin')
        op.create_index('ix_conv_memories_entities', 'conversation_memories', ['entities'], postgresql_using='gin')

    # Memory Insights table
    if not table_exists(connection, 'memory_insights'):
        op.create_table(
            'memory_insights',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),

            # Insight content
            sa.Column('insight_type', sa.String(30), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('content', sa.Text, nullable=False),

            # Priority and timing
            sa.Column('priority', sa.Integer, nullable=False, server_default='5'),
            sa.Column('urgency', sa.String(20), nullable=False, server_default='normal'),

            # Source memory
            sa.Column('source_memory_id', UUID(as_uuid=True), nullable=True),

            # Related entities
            sa.Column('related_memory_ids', ARRAY(UUID(as_uuid=True)), server_default='{}'),
            sa.Column('related_event_ids', ARRAY(UUID(as_uuid=True)), server_default='{}'),
            sa.Column('related_travel_ids', ARRAY(UUID(as_uuid=True)), server_default='{}'),
            sa.Column('related_member_ids', ARRAY(UUID(as_uuid=True)), server_default='{}'),

            # Action suggestions
            sa.Column('action_options', ARRAY(sa.String), server_default='{}'),
            sa.Column('action_data', JSONB, server_default='{}'),

            # Status
            sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
            sa.Column('shown_at', sa.DateTime, nullable=True),
            sa.Column('acted_at', sa.DateTime, nullable=True),
            sa.Column('dismissed_at', sa.DateTime, nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('expires_at', sa.DateTime, nullable=True),

            # Foreign keys
            sa.ForeignKeyConstraint(['source_memory_id'], ['conversation_memories.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('ix_memory_insights_user_id', 'memory_insights', ['user_id'])
        op.create_index('ix_memory_insights_family_id', 'memory_insights', ['family_id'])
        op.create_index('ix_memory_insights_type', 'memory_insights', ['insight_type'])
        op.create_index('ix_memory_insights_user_status', 'memory_insights', ['user_id', 'status'])
        op.create_index('ix_memory_insights_user_type', 'memory_insights', ['user_id', 'insight_type'])
        op.create_index('ix_memory_insights_priority', 'memory_insights', ['priority'])

    # Memory Associations table
    if not table_exists(connection, 'memory_associations'):
        op.create_table(
            'memory_associations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

            # The two memories being linked
            sa.Column('memory_id_a', UUID(as_uuid=True), nullable=False),
            sa.Column('memory_id_b', UUID(as_uuid=True), nullable=False),

            # Association metadata
            sa.Column('association_type', sa.String(30), nullable=False),
            sa.Column('strength', sa.Float, nullable=False, server_default='0.5'),
            sa.Column('reason', sa.Text, nullable=True),

            # Auto-generated or manual
            sa.Column('is_auto_generated', sa.Boolean, nullable=False, server_default='true'),

            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),

            # Foreign keys
            sa.ForeignKeyConstraint(['memory_id_a'], ['conversation_memories.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['memory_id_b'], ['conversation_memories.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('ix_memory_assoc_a', 'memory_associations', ['memory_id_a'])
        op.create_index('ix_memory_assoc_b', 'memory_associations', ['memory_id_b'])

        # Unique constraint to prevent duplicate associations
        op.create_unique_constraint(
            'uq_memory_associations_pair',
            'memory_associations',
            ['memory_id_a', 'memory_id_b', 'association_type']
        )


def downgrade():
    op.drop_table('memory_associations')
    op.drop_table('memory_insights')
    op.drop_table('conversation_memories')
