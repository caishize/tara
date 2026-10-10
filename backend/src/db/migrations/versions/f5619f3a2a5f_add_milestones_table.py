"""add_milestones_table

Revision ID: f5619f3a2a5f
Revises: feffd9a27204
Create Date: 2025-11-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'f5619f3a2a5f'
down_revision: Union[str, None] = 'feffd9a27204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'milestones',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('child_id', UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('event_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('achieved_date', sa.Date, nullable=False),
        sa.Column('age_in_months', sa.Integer, nullable=True),
        sa.Column('is_delayed', sa.String(10), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_milestones_family_id', 'milestones', ['family_id'])
    op.create_index('ix_milestones_child_id', 'milestones', ['child_id'])
    op.create_index('ix_milestones_category', 'milestones', ['category'])


def downgrade() -> None:
    op.drop_index('ix_milestones_category', 'milestones')
    op.drop_index('ix_milestones_child_id', 'milestones')
    op.drop_index('ix_milestones_family_id', 'milestones')
    op.drop_table('milestones')
