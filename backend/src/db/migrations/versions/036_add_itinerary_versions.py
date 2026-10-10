"""Add itinerary versions table for travel planning

Revision ID: 036_add_itinerary_versions
Revises: 035_create_secretary_memory_tables
Create Date: 2026-01-15 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '036_add_itinerary_versions'
down_revision: Union[str, None] = '035_secretary_memory'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create itinerary_versions table for storing multiple itinerary versions per trip
    op.create_table(
        'itinerary_versions',
        sa.Column('version_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trip_id', UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer, nullable=False),
        sa.Column('version_name', sa.String(200), nullable=True),  # e.g., "方案A - 紧凑型"
        sa.Column('style_tags', JSONB, nullable=True, server_default='[]'),  # e.g., ["intensive", "cultural"]
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('total_estimated_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('schedules', JSONB, nullable=False, server_default='[]'),  # Complete daily schedules data
        sa.Column('generation_config', JSONB, nullable=True),  # Store the config used for generation
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['trip_id'], ['travel_plans.trip_id'], ondelete='CASCADE'),
        sa.CheckConstraint('version_number > 0', name='check_version_number_positive'),
    )

    # Index for quick lookup by trip
    op.create_index('idx_itinerary_version_trip', 'itinerary_versions', ['trip_id', 'version_number'])

    # Index for finding active version
    op.create_index('idx_itinerary_version_active', 'itinerary_versions', ['trip_id', 'is_active'])


def downgrade() -> None:
    op.drop_index('idx_itinerary_version_active', 'itinerary_versions')
    op.drop_index('idx_itinerary_version_trip', 'itinerary_versions')
    op.drop_table('itinerary_versions')
