"""Create child growth tables

Revision ID: 004_create_child_growth_tables
Revises: 003_create_gift_tables
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_create_child_growth_tables'
down_revision = '003_create_gift_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create growth_records table
    op.create_table(
        'growth_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('child_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_type', sa.String(50), nullable=False),
        sa.Column('record_date', sa.Date, nullable=False),
        sa.Column('value', sa.Numeric(10, 2), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('idx_growth_child', 'growth_records', ['child_id'])
    op.create_index('idx_growth_type', 'growth_records', ['record_type'])
    op.create_index('idx_growth_date', 'growth_records', ['record_date'])

    # Create vaccine_records table
    op.create_table(
        'vaccine_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('child_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vaccine_name', sa.String(200), nullable=False),
        sa.Column('scheduled_date', sa.Date, nullable=False),
        sa.Column('completed_date', sa.Date, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('idx_vaccine_child', 'vaccine_records', ['child_id'])
    op.create_index('idx_vaccine_status', 'vaccine_records', ['status'])


def downgrade() -> None:
    op.drop_table('vaccine_records')
    op.drop_table('growth_records')
