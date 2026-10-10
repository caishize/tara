"""add partial unique index on event_associations (source_event_id, title)

Cleans up existing duplicate rows (keeps earliest created_at) and adds
a partial unique index WHERE NOT is_dismissed to prevent future duplicates.

Revision ID: 066_assoc_unique
Revises: 065_add_trip_context
Create Date: 2026-02-01
"""
from alembic import op

revision = "066_assoc_unique"
down_revision = "065_add_trip_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Remove duplicate rows — keep the earliest created_at per group
    op.execute("""
        DELETE FROM event_associations
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY source_event_id, title
                           ORDER BY created_at ASC
                       ) AS rn
                FROM event_associations
                WHERE NOT is_dismissed
            ) ranked
            WHERE ranked.rn > 1
        )
    """)

    # 2. Add partial unique index (only for non-dismissed associations)
    op.create_index(
        "uq_assoc_source_title_active",
        "event_associations",
        ["source_event_id", "title"],
        unique=True,
        postgresql_where="NOT is_dismissed",
    )


def downgrade() -> None:
    op.drop_index("uq_assoc_source_title_active", table_name="event_associations")
