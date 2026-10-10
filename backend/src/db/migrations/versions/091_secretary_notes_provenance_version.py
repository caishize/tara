"""Add provenance, version, superseded_by, contradiction_flags to secretary_notes.

Supports V8 version tracking, provenance chain, and contradiction detection
for the L1 fact base.

Revision ID: 091
Revises: 090
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "secretary_notes",
        sa.Column("provenance", JSONB, server_default="[]"),
    )
    op.add_column(
        "secretary_notes",
        sa.Column("version", sa.Integer, server_default="1", nullable=False),
    )
    op.add_column(
        "secretary_notes",
        sa.Column("superseded_by", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "secretary_notes",
        sa.Column("contradiction_flags", JSONB, server_default="[]"),
    )
    op.create_foreign_key(
        "fk_secretary_notes_superseded_by",
        "secretary_notes",
        "secretary_notes",
        ["superseded_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_secretary_notes_superseded_by",
        "secretary_notes",
        type_="foreignkey",
    )
    op.drop_column("secretary_notes", "contradiction_flags")
    op.drop_column("secretary_notes", "superseded_by")
    op.drop_column("secretary_notes", "version")
    op.drop_column("secretary_notes", "provenance")
