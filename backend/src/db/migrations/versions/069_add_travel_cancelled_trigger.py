"""Add travel_cancelled to curation job trigger types.

Revision ID: 069
Revises: 068
Create Date: 2026-02-05
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '069'
down_revision = '068'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old constraint and create new one with additional trigger types
    op.drop_constraint('check_job_trigger', 'curation_jobs', type_='check')
    op.create_check_constraint(
        'check_job_trigger',
        'curation_jobs',
        "trigger_type IN ('scheduled', 'event', 'manual', 'travel_cancelled', 'travel_created', 'travel_updated')"
    )


def downgrade() -> None:
    # Revert to original constraint
    op.drop_constraint('check_job_trigger', 'curation_jobs', type_='check')
    op.create_check_constraint(
        'check_job_trigger',
        'curation_jobs',
        "trigger_type IN ('scheduled', 'event', 'manual')"
    )
