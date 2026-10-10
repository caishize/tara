"""Rename travel_* trigger types to trip_* in curation_jobs check constraint.

Follows the travel→trip rename (migration 083). The code already uses
trip_created / trip_updated / trip_cancelled but the DB check constraint
still referenced travel_*.

Revision ID: 085
Revises: 084
"""
from alembic import op


revision = "085"
down_revision = "084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop constraint FIRST so UPDATE doesn't violate it
    op.drop_constraint("check_job_trigger", "curation_jobs", type_="check")

    # Rename existing rows from travel_* to trip_*
    op.execute(
        "UPDATE curation_jobs SET trigger_type = 'trip_created' "
        "WHERE trigger_type = 'travel_created'"
    )
    op.execute(
        "UPDATE curation_jobs SET trigger_type = 'trip_updated' "
        "WHERE trigger_type = 'travel_updated'"
    )
    op.execute(
        "UPDATE curation_jobs SET trigger_type = 'trip_cancelled' "
        "WHERE trigger_type = 'travel_cancelled'"
    )

    # Recreate constraint with trip_* names
    op.create_check_constraint(
        "check_job_trigger",
        "curation_jobs",
        "trigger_type IN ('scheduled', 'event', 'manual', "
        "'trip_created', 'trip_updated', 'trip_cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("check_job_trigger", "curation_jobs", type_="check")

    op.execute(
        "UPDATE curation_jobs SET trigger_type = 'travel_created' "
        "WHERE trigger_type = 'trip_created'"
    )
    op.execute(
        "UPDATE curation_jobs SET trigger_type = 'travel_updated' "
        "WHERE trigger_type = 'trip_updated'"
    )
    op.execute(
        "UPDATE curation_jobs SET trigger_type = 'travel_cancelled' "
        "WHERE trigger_type = 'trip_cancelled'"
    )

    op.create_check_constraint(
        "check_job_trigger",
        "curation_jobs",
        "trigger_type IN ('scheduled', 'event', 'manual', "
        "'travel_cancelled', 'travel_created', 'travel_updated')",
    )
