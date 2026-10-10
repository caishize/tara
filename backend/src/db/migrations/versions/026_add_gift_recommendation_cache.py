"""Add gift recommendation cache table

Revision ID: 026_recommendation_cache
Revises: 025_smart_events
Create Date: 2024-12-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '026_recommendation_cache'
down_revision = '025_smart_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create gift_recommendation_cache table."""
    op.create_table(
        'gift_recommendation_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),  # 'date', 'gift', 'travel'
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=True),  # 收礼人ID
        sa.Column('recommendations', postgresql.JSONB, nullable=False, server_default='[]'),  # 推荐结果JSON
        sa.Column('source', sa.String(20), nullable=False, server_default='llm'),  # 'llm' or 'rule'
        sa.Column('prompt_hash', sa.String(64), nullable=True),  # 用于检测输入是否变化
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),  # 可选的过期时间
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )

    # Create indexes for fast lookup
    op.create_index(
        'ix_gift_recommendation_cache_lookup',
        'gift_recommendation_cache',
        ['family_id', 'event_type', 'event_id', 'member_id'],
        unique=True
    )

    op.create_index(
        'ix_gift_recommendation_cache_family',
        'gift_recommendation_cache',
        ['family_id']
    )

    op.create_index(
        'ix_gift_recommendation_cache_event',
        'gift_recommendation_cache',
        ['event_type', 'event_id']
    )


def downgrade() -> None:
    """Drop gift_recommendation_cache table."""
    op.drop_index('ix_gift_recommendation_cache_event')
    op.drop_index('ix_gift_recommendation_cache_family')
    op.drop_index('ix_gift_recommendation_cache_lookup')
    op.drop_table('gift_recommendation_cache')
