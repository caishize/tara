"""Create preparation_items independent table.

Independent table for preparation checklists (replaces JSONB on curated_events).
Row-level locking enables concurrent item toggling without last-write-wins.

Revision ID: 080
Revises: 079
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "080"
down_revision = "079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preparation_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("curated_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "key",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("done", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Migrate existing JSONB data into the new table
    op.execute("""
        INSERT INTO preparation_items (id, event_id, key, text, source, done, sort_order, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            ce.id,
            COALESCE((item->>'key')::uuid, gen_random_uuid()),
            COALESCE(item->>'item', item->>'text', ''),
            COALESCE(item->>'source', 'manual'),
            COALESCE((item->>'done')::boolean, false),
            (row_number() OVER (PARTITION BY ce.id ORDER BY ordinality)) - 1,
            ce.created_at,
            ce.updated_at
        FROM curated_events ce,
             jsonb_array_elements(ce.preparation_items) WITH ORDINALITY AS t(item, ordinality)
        WHERE ce.preparation_items IS NOT NULL
          AND jsonb_array_length(ce.preparation_items) > 0
    """)


def downgrade() -> None:
    # Migrate data back to JSONB before dropping the table
    op.execute("""
        UPDATE curated_events ce
        SET preparation_items = sub.items
        FROM (
            SELECT
                pi.event_id,
                jsonb_agg(
                    jsonb_build_object(
                        'key', pi.key::text,
                        'item', pi.text,
                        'source', pi.source,
                        'done', pi.done
                    ) ORDER BY pi.sort_order
                ) AS items
            FROM preparation_items pi
            GROUP BY pi.event_id
        ) sub
        WHERE ce.id = sub.event_id
    """)
    op.drop_table("preparation_items")
