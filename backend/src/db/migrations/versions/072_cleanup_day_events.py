"""cleanup day shell events and migrate associations to trip-level events

After the trip atomization refactor, trips are stored as single CuratedEvents
instead of being decomposed into N "Day X · ..." events.  This migration:
1. Re-parents associations from Day shell events to their trip-level parent.
2. Deactivates Day shell events (kept for 30-day audit trail).

Revision ID: 072
Revises: 071
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1a: Delete duplicate associations that would violate the unique
    # constraint when re-parented.  If the trip-level event already has an
    # association with the same title, we keep the trip-level one and drop
    # the Day-level duplicate.
    conn.execute(sa.text("""
        DELETE FROM event_associations
        WHERE id IN (
            SELECT ea.id
            FROM event_associations ea
            JOIN curated_events day_event
              ON ea.source_event_id = day_event.id
              AND day_event.title LIKE 'Day %% · %%'
              AND day_event.trip_id IS NOT NULL
            JOIN curated_events trip_event
              ON day_event.trip_id = trip_event.trip_id
              AND trip_event.event_type IN ('business_trip', 'travel')
              AND trip_event.title NOT LIKE 'Day %% · %%'
              AND trip_event.is_active = true
            WHERE EXISTS (
                SELECT 1 FROM event_associations existing
                WHERE existing.source_event_id = trip_event.id
                  AND existing.title = ea.title
            )
        )
    """))

    # Step 1b: Among Day-level associations that map to the same trip-level
    # event, keep only one per title (the newest by created_at).
    conn.execute(sa.text("""
        DELETE FROM event_associations
        WHERE id IN (
            SELECT ea.id
            FROM event_associations ea
            JOIN curated_events day_event
              ON ea.source_event_id = day_event.id
              AND day_event.title LIKE 'Day %% · %%'
              AND day_event.trip_id IS NOT NULL
            JOIN curated_events trip_event
              ON day_event.trip_id = trip_event.trip_id
              AND trip_event.event_type IN ('business_trip', 'travel')
              AND trip_event.title NOT LIKE 'Day %% · %%'
              AND trip_event.is_active = true
            WHERE ea.id != (
                SELECT ea2.id
                FROM event_associations ea2
                JOIN curated_events de2
                  ON ea2.source_event_id = de2.id
                  AND de2.trip_id = day_event.trip_id
                  AND de2.title LIKE 'Day %% · %%'
                WHERE ea2.title = ea.title
                ORDER BY ea2.created_at DESC
                LIMIT 1
            )
        )
    """))

    # Step 1c: Migrate remaining associations from Day shell events to the
    # trip-level event.  Duplicates were removed above so this is safe.
    conn.execute(sa.text("""
        UPDATE event_associations ea
        SET source_event_id = trip_event.id
        FROM curated_events day_event
        JOIN curated_events trip_event
          ON day_event.trip_id = trip_event.trip_id
          AND trip_event.event_type IN ('business_trip', 'travel')
          AND trip_event.title NOT LIKE 'Day %% · %%'
          AND trip_event.is_active = true
        WHERE ea.source_event_id = day_event.id
          AND day_event.title LIKE 'Day %% · %%'
          AND day_event.trip_id IS NOT NULL
    """))

    # Step 2: Deactivate ALL Day shell events — both those with trip_id and
    # orphaned ones (trip_id IS NULL) left behind by previous deletions.
    conn.execute(sa.text("""
        UPDATE curated_events
        SET is_active = false, status = 'cancelled'
        WHERE title LIKE 'Day %% · %%'
          AND is_active = true
    """))


def downgrade() -> None:
    # Re-activation is safe; association re-parenting is not easily reversible
    # but Day events can be re-activated so the app works as before.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE curated_events
        SET is_active = true
        WHERE title LIKE 'Day %% · %%'
          AND trip_id IS NOT NULL
          AND is_active = false
    """))
