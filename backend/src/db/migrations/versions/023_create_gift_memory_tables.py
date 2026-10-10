"""
Create gift memory and conversation context tables.

Revision ID: 023_gift_memory
Revises: 022_gift_orchestration
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers
revision = '023_gift_memory'
down_revision = '022_gift_orchestration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create gift_conversation_context table
    op.create_table(
        'gift_conversation_context',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', UUID(as_uuid=True), nullable=True),
        sa.Column('conversation_id', UUID(as_uuid=True), nullable=True),
        sa.Column('recommendation_id', UUID(as_uuid=True), nullable=True),

        # Context Type
        sa.Column('context_type', sa.String(50), nullable=False),

        # Extracted Content
        sa.Column('raw_text', sa.Text, nullable=False),
        sa.Column('extracted_value', sa.Text, nullable=True),
        sa.Column('extracted_data', JSONB, nullable=True),

        # Categories Affected
        sa.Column('affected_categories', ARRAY(sa.String(50)), nullable=True),

        # Sentiment & Confidence
        sa.Column('sentiment', sa.String(20), nullable=True),
        sa.Column('confidence', sa.Float, nullable=False, server_default='0.8'),

        # Validity
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime, nullable=True),

        # Source
        sa.Column('source', sa.String(50), nullable=False, server_default='conversation'),

        # Timestamps
        sa.Column('mentioned_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for gift_conversation_context
    op.create_index('idx_conv_ctx_family', 'gift_conversation_context', ['family_id'])
    op.create_index('idx_conv_ctx_member', 'gift_conversation_context', ['member_id'])
    op.create_index('idx_conv_ctx_type', 'gift_conversation_context', ['context_type'])
    op.create_index('idx_conv_ctx_active', 'gift_conversation_context', ['is_active'])
    op.create_index('idx_conv_ctx_mentioned', 'gift_conversation_context', ['mentioned_at'])

    # Create member_gift_memory table
    op.create_table(
        'member_gift_memory',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', UUID(as_uuid=True), nullable=False, unique=True),

        # Gift History Summary
        sa.Column('total_gifts_received', sa.Integer, nullable=False, server_default='0'),
        sa.Column('gifts_last_year', sa.Integer, nullable=False, server_default='0'),
        sa.Column('gifts_last_3_years', sa.Integer, nullable=False, server_default='0'),
        sa.Column('recent_gifts', JSONB, nullable=True),
        sa.Column('category_counts', JSONB, nullable=True),
        sa.Column('gifts_to_avoid', JSONB, nullable=True),

        # Preference Summary
        sa.Column('liked_categories', ARRAY(sa.String(50)), nullable=True),
        sa.Column('disliked_categories', ARRAY(sa.String(50)), nullable=True),
        sa.Column('brand_preferences', JSONB, nullable=True),
        sa.Column('typical_price_min', sa.Float, nullable=True),
        sa.Column('typical_price_max', sa.Float, nullable=True),
        sa.Column('preference_scores', JSONB, nullable=True),

        # Conversation Context Summary
        sa.Column('conversation_insights', JSONB, nullable=True),
        sa.Column('interest_keywords', ARRAY(sa.String(100)), nullable=True),

        # Relationship Context
        sa.Column('relationship_type', sa.String(50), nullable=True),
        sa.Column('intimacy_level', sa.Integer, nullable=True),
        sa.Column('special_notes', sa.Text, nullable=True),

        # Recommendation History
        sa.Column('total_recommendations', sa.Integer, nullable=False, server_default='0'),
        sa.Column('accepted_recommendations', sa.Integer, nullable=False, server_default='0'),
        sa.Column('acceptance_rate', sa.Float, nullable=True),
        sa.Column('last_recommended_items', JSONB, nullable=True),

        # Occasion History
        sa.Column('occasions_history', JSONB, nullable=True),

        # Metadata
        sa.Column('last_gift_date', sa.DateTime, nullable=True),
        sa.Column('last_recommendation_date', sa.DateTime, nullable=True),
        sa.Column('last_conversation_update', sa.DateTime, nullable=True),
        sa.Column('memory_richness_score', sa.Float, nullable=False, server_default='0.0'),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for member_gift_memory
    op.create_index('idx_gift_memory_family', 'member_gift_memory', ['family_id'])
    op.create_index('idx_gift_memory_member', 'member_gift_memory', ['member_id'])
    op.create_index('idx_gift_memory_updated', 'member_gift_memory', ['updated_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_gift_memory_updated', table_name='member_gift_memory')
    op.drop_index('idx_gift_memory_member', table_name='member_gift_memory')
    op.drop_index('idx_gift_memory_family', table_name='member_gift_memory')

    op.drop_index('idx_conv_ctx_mentioned', table_name='gift_conversation_context')
    op.drop_index('idx_conv_ctx_active', table_name='gift_conversation_context')
    op.drop_index('idx_conv_ctx_type', table_name='gift_conversation_context')
    op.drop_index('idx_conv_ctx_member', table_name='gift_conversation_context')
    op.drop_index('idx_conv_ctx_family', table_name='gift_conversation_context')

    # Drop tables
    op.drop_table('member_gift_memory')
    op.drop_table('gift_conversation_context')
