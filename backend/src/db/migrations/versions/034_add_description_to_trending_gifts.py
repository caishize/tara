"""Add description column to trending_gifts table

Revision ID: 034_trending_gift_desc
Revises: 033_create_trending_gifts_tables
Create Date: 2025-01-11
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '034_trending_gift_desc'
down_revision = '033_create_trending_gifts_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add description column for storing recommendation reasons."""
    op.add_column(
        'trending_gifts',
        sa.Column('description', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    """Remove description column."""
    op.drop_column('trending_gifts', 'description')
