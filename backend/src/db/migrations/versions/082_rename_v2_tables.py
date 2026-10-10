"""Rename v2-suffixed tables to clean names.

Drop legacy V1 tables (favor_records, contacts) that are unused,
then rename favor_records_v2 → favor_records, social_events_v2 → social_events,
and update all index names.

Revision ID: 082
Revises: 081
"""
from alembic import op

revision = "082"
down_revision = "081"


def upgrade():
    # 1. Drop legacy V1 tables if they exist (created by migration 006, never used)
    op.execute("DROP TABLE IF EXISTS favor_records CASCADE")
    op.execute("DROP TABLE IF EXISTS contacts CASCADE")
    op.execute("DROP TABLE IF EXISTS social_events CASCADE")

    # 2. Rename social_events_v2 → social_events
    op.rename_table("social_events_v2", "social_events")
    op.execute("ALTER INDEX idx_event_v2_family_date RENAME TO idx_event_family_date")
    op.execute("ALTER INDEX idx_event_v2_status RENAME TO idx_event_status")

    # 3. Rename favor_records_v2 → favor_records
    #    Must update FK constraint first (references social_events_v2 which is now social_events)
    op.rename_table("favor_records_v2", "favor_records")
    op.execute("ALTER INDEX idx_favor_v2_family_contact RENAME TO idx_favor_family_contact")
    op.execute("ALTER INDEX idx_favor_v2_family_date RENAME TO idx_favor_family_date")
    op.execute("ALTER INDEX idx_favor_v2_status RENAME TO idx_favor_status")
    # idx_favor_v2_event → idx_favor_event (if exists)
    op.execute("ALTER INDEX IF EXISTS idx_favor_v2_event RENAME TO idx_favor_event")


def downgrade():
    # Reverse the renames
    op.rename_table("favor_records", "favor_records_v2")
    op.rename_table("social_events", "social_events_v2")

    op.execute("ALTER INDEX idx_event_family_date RENAME TO idx_event_v2_family_date")
    op.execute("ALTER INDEX idx_event_status RENAME TO idx_event_v2_status")
    op.execute("ALTER INDEX idx_favor_family_contact RENAME TO idx_favor_v2_family_contact")
    op.execute("ALTER INDEX idx_favor_family_date RENAME TO idx_favor_v2_family_date")
    op.execute("ALTER INDEX idx_favor_status RENAME TO idx_favor_v2_status")
    op.execute("ALTER INDEX IF EXISTS idx_favor_event RENAME TO idx_favor_v2_event")
