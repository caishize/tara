"""Create gift orchestration tables

Revision ID: 022_gift_orchestration
Revises: 020_add_renqing_tables
Create Date: 2024-12-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '022_gift_orchestration'
down_revision: Union[str, None] = '020_add_renqing_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gift_tasks table
    op.create_table(
        'gift_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('important_date_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Occasion info
        sa.Column('occasion', sa.String(50), nullable=False),
        sa.Column('occasion_date', sa.Date, nullable=False),
        sa.Column('occasion_title', sa.String(200), nullable=True),

        # Scheduling
        sa.Column('scheduled_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trigger_source', sa.String(50), nullable=False, server_default='auto_date'),

        # Budget
        sa.Column('budget_min', sa.Integer, nullable=True),
        sa.Column('budget_max', sa.Integer, nullable=True),

        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),

        # Result
        sa.Column('recommendation_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Error handling
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='3'),

        # Processing info
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_time_ms', sa.Integer, nullable=True),

        # Metadata
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes for gift_tasks
    op.create_index('idx_gift_task_family', 'gift_tasks', ['family_id'])
    op.create_index('idx_gift_task_status', 'gift_tasks', ['status'])
    op.create_index('idx_gift_task_scheduled', 'gift_tasks', ['scheduled_time'])
    op.create_index('idx_gift_task_member', 'gift_tasks', ['member_id'])
    op.create_index('idx_gift_task_date', 'gift_tasks', ['important_date_id'])
    op.create_index('idx_gift_task_occasion_date', 'gift_tasks', ['occasion_date'])

    # Unique constraint for one task per date per year
    op.create_index(
        'idx_gift_task_unique_date_year',
        'gift_tasks',
        ['important_date_id', 'occasion_date'],
        unique=True,
        postgresql_where=sa.text('is_deleted = false')
    )

    # Add new columns to gift_recommendations table
    # These columns enhance the recommendation with context information
    try:
        op.add_column('gift_recommendations',
            sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.add_column('gift_recommendations',
            sa.Column('member_profile_snapshot', postgresql.JSONB, nullable=True)
        )
        op.add_column('gift_recommendations',
            sa.Column('relation_context', postgresql.JSONB, nullable=True)
        )
        op.add_column('gift_recommendations',
            sa.Column('dedup_analysis', postgresql.JSONB, nullable=True)
        )
        op.add_column('gift_recommendations',
            sa.Column('personalization_score', sa.Float, nullable=True)
        )
        op.create_index('idx_recommendation_task', 'gift_recommendations', ['task_id'])
    except Exception:
        pass  # Columns might already exist

    # Add new columns to gift_history table
    try:
        op.add_column('gift_history',
            sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.add_column('gift_history',
            sa.Column('selected_option_index', sa.Integer, nullable=True)
        )
        op.add_column('gift_history',
            sa.Column('feedback_comment', sa.Text, nullable=True)
        )
        op.add_column('gift_history',
            sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True)
        )
        op.create_index('idx_history_task', 'gift_history', ['task_id'])
    except Exception:
        pass  # Columns might already exist


def downgrade() -> None:
    # Remove new columns from gift_history
    try:
        op.drop_index('idx_history_task', table_name='gift_history')
        op.drop_column('gift_history', 'feedback_at')
        op.drop_column('gift_history', 'feedback_comment')
        op.drop_column('gift_history', 'selected_option_index')
        op.drop_column('gift_history', 'task_id')
    except Exception:
        pass

    # Remove new columns from gift_recommendations
    try:
        op.drop_index('idx_recommendation_task', table_name='gift_recommendations')
        op.drop_column('gift_recommendations', 'personalization_score')
        op.drop_column('gift_recommendations', 'dedup_analysis')
        op.drop_column('gift_recommendations', 'relation_context')
        op.drop_column('gift_recommendations', 'member_profile_snapshot')
        op.drop_column('gift_recommendations', 'task_id')
    except Exception:
        pass

    # Drop gift_tasks table
    op.drop_index('idx_gift_task_unique_date_year', table_name='gift_tasks')
    op.drop_index('idx_gift_task_occasion_date', table_name='gift_tasks')
    op.drop_index('idx_gift_task_date', table_name='gift_tasks')
    op.drop_index('idx_gift_task_member', table_name='gift_tasks')
    op.drop_index('idx_gift_task_scheduled', table_name='gift_tasks')
    op.drop_index('idx_gift_task_status', table_name='gift_tasks')
    op.drop_index('idx_gift_task_family', table_name='gift_tasks')
    op.drop_table('gift_tasks')
