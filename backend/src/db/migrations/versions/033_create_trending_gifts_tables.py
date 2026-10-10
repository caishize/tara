"""Create trending gifts tables

Revision ID: 033_create_trending_gifts_tables
Revises: 032_create_research_sessions
Create Date: 2026-01-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '033_create_trending_gifts_tables'
down_revision = '032_research_sessions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create trending_gifts table
    op.create_table(
        'trending_gifts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('brand', sa.String(200), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('original_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('discount_percent', sa.Integer, nullable=True),
        sa.Column('rating', sa.Numeric(2, 1), nullable=True),
        sa.Column('review_count', sa.Integer, nullable=True, server_default='0'),
        sa.Column('image_url', sa.String(1000), nullable=True),
        sa.Column('product_url', sa.String(1000), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('data_source', sa.String(50), nullable=False),
        sa.Column('popularity_score', sa.Integer, nullable=True, server_default='0'),
        sa.Column('rank', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_verified_at', sa.TIMESTAMP, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        # Constraints
        sa.CheckConstraint('price >= 0', name='ck_trending_gifts_price_positive'),
        sa.CheckConstraint('original_price IS NULL OR original_price >= 0', name='ck_trending_gifts_original_price_positive'),
        sa.CheckConstraint('discount_percent IS NULL OR (discount_percent >= 0 AND discount_percent <= 100)', name='ck_trending_gifts_discount_range'),
        sa.CheckConstraint('rating IS NULL OR (rating >= 0 AND rating <= 5)', name='ck_trending_gifts_rating_range'),
    )

    # Create indexes for trending_gifts
    op.create_index('idx_trending_gift_category', 'trending_gifts', ['category', 'is_active'])
    op.create_index('idx_trending_gift_source', 'trending_gifts', ['data_source', 'created_at'])
    op.create_index('idx_trending_gift_external', 'trending_gifts', ['external_id', 'data_source'], unique=True)
    op.create_index('idx_trending_gift_popularity', 'trending_gifts', ['popularity_score', 'is_active'])
    op.create_index('idx_trending_gift_rank', 'trending_gifts', ['category', 'rank'])

    # 2. Create occasions table
    op.create_table(
        'occasions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('name_en', sa.String(100), nullable=True, unique=True),
        sa.Column('date_type', sa.String(20), nullable=False),  # solar, lunar, relative
        sa.Column('solar_date', sa.String(10), nullable=True),  # MM-DD format
        sa.Column('lunar_month', sa.Integer, nullable=True),
        sa.Column('lunar_day', sa.Integer, nullable=True),
        sa.Column('week_ordinal', sa.Integer, nullable=True),  # 1-5 for nth week
        sa.Column('weekday', sa.Integer, nullable=True),  # 0-6 for Mon-Sun
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('gift_categories', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        # Constraints
        sa.CheckConstraint("date_type IN ('solar', 'lunar', 'relative')", name='ck_occasions_date_type'),
        sa.CheckConstraint('lunar_month IS NULL OR (lunar_month >= 1 AND lunar_month <= 12)', name='ck_occasions_lunar_month'),
        sa.CheckConstraint('lunar_day IS NULL OR (lunar_day >= 1 AND lunar_day <= 30)', name='ck_occasions_lunar_day'),
        sa.CheckConstraint('week_ordinal IS NULL OR (week_ordinal >= 1 AND week_ordinal <= 5)', name='ck_occasions_week_ordinal'),
        sa.CheckConstraint('weekday IS NULL OR (weekday >= 0 AND weekday <= 6)', name='ck_occasions_weekday'),
    )

    # Create index for occasions
    op.create_index('idx_occasions_active', 'occasions', ['is_active'])
    op.create_index('idx_occasions_date_type', 'occasions', ['date_type'])

    # 3. Create occasion_gifts table (many-to-many relationship)
    op.create_table(
        'occasion_gifts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('occasion_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('occasions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gift_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trending_gifts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=True, server_default='0'),
        sa.Column('match_reason', sa.String(200), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )

    # Create indexes for occasion_gifts
    op.create_index('idx_occasion_gift_occasion', 'occasion_gifts', ['occasion_id', 'sort_order'])
    op.create_index('idx_occasion_gift_unique', 'occasion_gifts', ['occasion_id', 'gift_id'], unique=True)
    op.create_index('idx_occasion_gift_gift', 'occasion_gifts', ['gift_id'])

    # 4. Create data_sources table
    op.create_table(
        'data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('source_type', sa.String(50), nullable=False),  # scraper, api
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('config', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer, nullable=True, server_default='0'),
        sa.Column('last_fetch_at', sa.TIMESTAMP, nullable=True),
        sa.Column('error_count', sa.Integer, nullable=True, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )

    # Create index for data_sources
    op.create_index('idx_data_sources_active', 'data_sources', ['is_active', 'priority'])

    # 5. Create update_logs table
    op.create_table(
        'update_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', sa.String(100), nullable=True, unique=True),
        sa.Column('started_at', sa.TIMESTAMP, nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),  # running, success, failed, partial
        sa.Column('gifts_added', sa.Integer, nullable=True, server_default='0'),
        sa.Column('gifts_updated', sa.Integer, nullable=True, server_default='0'),
        sa.Column('gifts_deleted', sa.Integer, nullable=True, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('source_stats', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        # Constraints
        sa.CheckConstraint("status IN ('running', 'success', 'failed', 'partial')", name='ck_update_logs_status'),
    )

    # Create indexes for update_logs
    op.create_index('idx_update_logs_started', 'update_logs', ['started_at'])
    op.create_index('idx_update_logs_status', 'update_logs', ['status'])

    # 6. Create user_gift_saves table
    op.create_table(
        'user_gift_saves',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),  # No FK constraint - users table may not exist
        sa.Column('gift_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trending_gifts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('saved_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('note', sa.String(500), nullable=True),
    )

    # Create indexes for user_gift_saves
    op.create_index('idx_user_gift_save_user', 'user_gift_saves', ['user_id', 'saved_at'])
    op.create_index('idx_user_gift_save_unique', 'user_gift_saves', ['user_id', 'gift_id'], unique=True)
    op.create_index('idx_user_gift_save_gift', 'user_gift_saves', ['gift_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('user_gift_saves')
    op.drop_table('update_logs')
    op.drop_table('data_sources')
    op.drop_table('occasion_gifts')
    op.drop_table('occasions')
    op.drop_table('trending_gifts')
