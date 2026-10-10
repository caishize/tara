"""Create job_executions table for unified scheduler

Revision ID: 028_job_executions
Revises: 027_extend_shopping_integration
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '028_job_executions'
down_revision = '027_shopping_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create job_executions table for tracking scheduler task history."""

    # Create job_executions table
    op.create_table(
        'job_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_name', sa.String(100), nullable=False),
        sa.Column('scheduler_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('trigger_type', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_traceback', sa.Text, nullable=True),
        sa.Column('result_summary', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create indexes for efficient querying
    op.create_index(
        'idx_job_executions_job',
        'job_executions',
        ['job_name', 'created_at'],
        postgresql_ops={'created_at': 'DESC'}
    )

    op.create_index(
        'idx_job_executions_scheduler',
        'job_executions',
        ['scheduler_name', 'created_at'],
        postgresql_ops={'created_at': 'DESC'}
    )

    op.create_index(
        'idx_job_executions_status',
        'job_executions',
        ['status', 'created_at'],
        postgresql_ops={'created_at': 'DESC'}
    )

    # Create optional scheduler_configs table for persistent configuration
    op.create_table(
        'scheduler_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('scheduler_type', sa.String(20), nullable=False),
        sa.Column('config', postgresql.JSONB, nullable=False),
        sa.Column('is_enabled', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop job_executions and scheduler_configs tables."""
    op.drop_table('scheduler_configs')
    op.drop_index('idx_job_executions_status', table_name='job_executions')
    op.drop_index('idx_job_executions_scheduler', table_name='job_executions')
    op.drop_index('idx_job_executions_job', table_name='job_executions')
    op.drop_table('job_executions')
