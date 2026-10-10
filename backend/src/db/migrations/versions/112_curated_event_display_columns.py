"""Add typed display columns to curated_events for LLM pre-generation.

Revision ID: 112
Revises: 111

Adds life_context_hint, secretary_note, prep_hint, and enrichment_generated_at
to curated_events. These columns store pre-generated warm content from the
Curation Enrichment Phase (Haiku at curation time), replacing hardcoded
_HINT_MAP lookups at query time.
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


revision = "112"
down_revision = "111"


def _table_exists(connection, table_name: str) -> bool:
    result = connection.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_name = :t"
            ")"
        ),
        {"t": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "curated_events"):
        return

    op.add_column(
        "curated_events",
        sa.Column(
            "life_context_hint",
            sa.String(200),
            nullable=True,
            comment="Pre-generated warm context hint (Haiku at curation time)",
        ),
    )
    op.add_column(
        "curated_events",
        sa.Column(
            "secretary_note",
            sa.Text,
            nullable=True,
            comment="Pre-generated secretary annotation (Haiku at curation time)",
        ),
    )
    op.add_column(
        "curated_events",
        sa.Column(
            "prep_hint",
            sa.String(200),
            nullable=True,
            comment="Pre-generated preparation hint (Haiku at curation time)",
        ),
    )
    op.add_column(
        "curated_events",
        sa.Column(
            "enrichment_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when enrichment fields were last generated",
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "curated_events"):
        return

    op.drop_column("curated_events", "enrichment_generated_at")
    op.drop_column("curated_events", "prep_hint")
    op.drop_column("curated_events", "secretary_note")
    op.drop_column("curated_events", "life_context_hint")
