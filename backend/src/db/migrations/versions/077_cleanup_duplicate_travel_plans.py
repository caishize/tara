"""Merge historical duplicate travel plans.

For each family, finds travel_plans with the same destination (case-insensitive)
and overlapping date ranges.  Keeps the most recently updated trip and marks
the rest as cancelled so they no longer appear in queries.

Also deactivates curated_events that reference cancelled trips to prevent
orphaned timeline entries.

Revision ID: 077
Revises: 076
"""

from alembic import op
import sqlalchemy as sa

revision = "077"
down_revision = "076"


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Find duplicate groups and cancel the losers.
    # ROW_NUMBER partitions by family + destination; the self-join ensures
    # only trips with *overlapping* date ranges are treated as duplicates.
    # Non-overlapping trips (e.g., same destination in Jan and Jul) are kept.
    result = conn.execute(sa.text("""
        WITH ranked AS (
            SELECT
                trip_id,
                family_id,
                LOWER(destination) AS dest_lower,
                start_date,
                end_date,
                ROW_NUMBER() OVER (
                    PARTITION BY family_id, LOWER(destination)
                    ORDER BY (end_date - start_date) DESC, updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                ) AS rn
            FROM travel_plans
            WHERE status NOT IN ('cancelled', 'completed')
              AND destination IS NOT NULL
              AND start_date IS NOT NULL
              AND end_date IS NOT NULL
        ),
        duplicates AS (
            SELECT r2.trip_id
            FROM ranked r1
            JOIN ranked r2
              ON r1.family_id = r2.family_id
             AND r1.dest_lower = r2.dest_lower
             AND r1.rn = 1
             AND r2.rn > 1
             AND r1.start_date <= r2.end_date
             AND r1.end_date >= r2.start_date
        )
        UPDATE travel_plans
        SET status = 'cancelled',
            updated_at = NOW()
        WHERE trip_id IN (SELECT trip_id FROM duplicates)
        RETURNING trip_id
    """))
    cancelled_ids = [row[0] for row in result]

    # Step 2: Deactivate curated_events referencing cancelled trips.
    if cancelled_ids:
        conn.execute(sa.text("""
            UPDATE curated_events
            SET is_active = false,
                status = 'cancelled'
            WHERE trip_id = ANY(:ids)
              AND is_active = true
        """), {"ids": cancelled_ids})


def downgrade() -> None:
    # Cannot reliably un-cancel trips; this is a data cleanup migration.
    pass
