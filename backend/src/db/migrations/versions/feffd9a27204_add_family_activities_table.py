"""Add family_activities table

Revision ID: feffd9a27204
Revises: 006_create_relationship_tables
Create Date: 2025-11-23 00:43:01.299406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TIMESTAMP


# revision identifiers, used by Alembic.
revision: str = 'feffd9a27204'
down_revision: Union[str, None] = '006_create_relationship_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'family_activities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('activity_date', sa.DateTime, nullable=False),
        sa.Column('location', sa.String(300), nullable=True),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='planned'),
        sa.Column('participants', ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column('budget', sa.Float, nullable=True),
        sa.Column('actual_cost', sa.Float, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('photos', ARRAY(sa.String), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_family_activities_family_id', 'family_activities', ['family_id'])


def downgrade() -> None:
    op.drop_index('ix_family_activities_family_id', 'family_activities')
    op.drop_table('family_activities')
