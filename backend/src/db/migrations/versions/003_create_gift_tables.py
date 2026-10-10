"""Create gift recommendation tables

Revision ID: 003_create_gift_tables
Revises: 002_create_date_tables
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_create_gift_tables'
down_revision = '002_create_date_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create gift_recommendations table
    op.create_table(
        'gift_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('recipient_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('requester_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('related_date_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Recommendation context
        sa.Column('occasion', sa.String(50), nullable=False),
        sa.Column('occasion_date', sa.Date, nullable=True),
        sa.Column('trigger_source', sa.String(50), nullable=False),

        # Budget constraints
        sa.Column('budget_min', sa.Numeric(10, 2), nullable=True),
        sa.Column('budget_max', sa.Numeric(10, 2), nullable=True),

        # User preferences
        sa.Column('user_preferences', sa.Text, nullable=True),

        # Recommendation results (JSONB)
        sa.Column('recommendations', postgresql.JSONB, nullable=False),

        # Metadata
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('selected_option_index', sa.Integer, nullable=True),

        # Deduplication context
        sa.Column('excluded_categories', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('dedup_warnings', postgresql.JSONB, nullable=True),

        # LLM generation metadata
        sa.Column('llm_prompt', sa.Text, nullable=True),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('generation_time_ms', sa.Integer, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('viewed_at', sa.TIMESTAMP, nullable=True),
        sa.Column('selected_at', sa.TIMESTAMP, nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP, nullable=True),
    )

    # Create indexes for gift_recommendations
    op.create_index('idx_recommendation_family', 'gift_recommendations', ['family_id'])
    op.create_index('idx_recommendation_recipient', 'gift_recommendations', ['recipient_member_id'])
    op.create_index('idx_recommendation_status', 'gift_recommendations', ['status'])
    op.create_index('idx_recommendation_occasion', 'gift_recommendations', ['occasion'])
    op.create_index('idx_recommendation_created', 'gift_recommendations', ['created_at'])

    # Create gift_history table
    op.create_table(
        'gift_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('giver_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recipient_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recommendation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('related_date_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Gift info
        sa.Column('gift_name', sa.String(200), nullable=False),
        sa.Column('gift_category', sa.String(50), nullable=False),
        sa.Column('gift_description', sa.Text, nullable=True),

        # Occasion
        sa.Column('occasion', sa.String(50), nullable=False),
        sa.Column('occasion_date', sa.Date, nullable=False),

        # Price (encrypted)
        sa.Column('gift_price', sa.Text, nullable=True),

        # Purchase info
        sa.Column('purchase_link', sa.String(500), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),

        # Metadata
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),

        # Feedback
        sa.Column('feedback_rating', sa.String(20), nullable=True),
        sa.Column('feedback_text', sa.Text, nullable=True),
        sa.Column('feedback_collected_at', sa.DateTime, nullable=True),

        # Deduplication context
        sa.Column('is_duplicate', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('similar_history_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )

    # Create indexes for gift_history
    op.create_index('idx_history_family', 'gift_history', ['family_id'])
    op.create_index('idx_history_giver', 'gift_history', ['giver_user_id'])
    op.create_index('idx_history_recipient', 'gift_history', ['recipient_member_id'])
    op.create_index('idx_history_category', 'gift_history', ['gift_category'])
    op.create_index('idx_history_occasion_date', 'gift_history', ['occasion_date'])
    op.create_index('idx_history_created', 'gift_history', ['created_at'])

    # Create gift_preferences table
    op.create_table(
        'gift_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Preference context
        sa.Column('gift_category', sa.String(50), nullable=False),

        # Preference scoring
        sa.Column('preference_score', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('confidence', sa.Float, nullable=False, server_default='0.5'),

        # Learning source
        sa.Column('source', sa.String(50), nullable=False),

        # Feedback count
        sa.Column('feedback_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('positive_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('negative_count', sa.Integer, nullable=False, server_default='0'),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('last_feedback_at', sa.TIMESTAMP, nullable=True),
    )

    # Create indexes for gift_preferences
    op.create_index('idx_preference_family', 'gift_preferences', ['family_id'])
    op.create_index('idx_preference_member', 'gift_preferences', ['member_id'])
    op.create_index('idx_preference_category', 'gift_preferences', ['gift_category'])
    op.create_index('idx_preference_member_category', 'gift_preferences', ['member_id', 'gift_category'], unique=True)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('gift_preferences')
    op.drop_table('gift_history')
    op.drop_table('gift_recommendations')
