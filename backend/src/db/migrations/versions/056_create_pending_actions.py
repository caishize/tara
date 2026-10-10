"""Create pending_actions table for action confirmation flow.

Revision ID: 056_create_pending_actions
Revises: 055_enhance_timeline_and_graph
Create Date: 2025-01-28

This migration adds:
1. pending_actions table - Store actions awaiting user confirmation
2. Indexes for efficient querying by user and status

Based on: docs/New_Architecture.md - Action Decoupling pattern
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '056_create_pending_actions'
down_revision = '055_enhance_timeline_and_graph'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1. Create pending_actions table
    # ============================================
    op.create_table(
        'pending_actions',
        # Primary key
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # User and family reference
        sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),

        # Job reference (links to the originating agent task)
        sa.Column('job_id', UUID(as_uuid=True), nullable=True),

        # Action details
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('display_data', JSONB, nullable=True),

        # Status tracking
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),

        # Expiration
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),

        # Execution result
        sa.Column('execution_result', JSONB, nullable=True),

        # Error tracking
        sa.Column('error_message', sa.Text, nullable=True),

        # Constraints
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'expired', 'executed', 'failed')",
            name='ck_pending_actions_status'
        ),
    )

    # ============================================
    # 2. Create indexes
    # ============================================

    # Index for finding pending actions by user
    op.create_index(
        'ix_pending_actions_user_status',
        'pending_actions',
        ['user_id', 'status']
    )

    # Index for expiration cleanup job
    op.create_index(
        'ix_pending_actions_expires',
        'pending_actions',
        ['expires_at'],
        postgresql_where=sa.text("status = 'pending'")
    )

    # Index for job reference
    op.create_index(
        'ix_pending_actions_job_id',
        'pending_actions',
        ['job_id'],
        postgresql_where=sa.text('job_id IS NOT NULL')
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_pending_actions_job_id', 'pending_actions')
    op.drop_index('ix_pending_actions_expires', 'pending_actions')
    op.drop_index('ix_pending_actions_user_status', 'pending_actions')

    # Drop table
    op.drop_table('pending_actions')
