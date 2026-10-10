"""Add DiffApply fingerprint columns to curated_events and event_associations.

Revision ID: 097
Revises: 096

Adds stable_key, source_fingerprint, semantic_fingerprint to both tables
for idempotent change detection during diff/upsert curation cycles.
"""

from alembic import op
import sqlalchemy as sa


revision = "097"
down_revision = "096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- curated_events --
    op.add_column(
        "curated_events",
        sa.Column(
            "stable_key",
            sa.String(500),
            nullable=True,
            unique=True,
            comment="Deterministic identity key: event_type + entity IDs for cross-curation dedup",
        ),
    )
    op.add_column(
        "curated_events",
        sa.Column(
            "source_fingerprint",
            sa.String(64),
            nullable=True,
            comment="MD5 of source data that produced this event",
        ),
    )
    op.add_column(
        "curated_events",
        sa.Column(
            "semantic_fingerprint",
            sa.String(64),
            nullable=True,
            comment="MD5 of semantic content (title+start+end+location+type)",
        ),
    )
    op.create_index(
        "ix_curated_events_stable_key",
        "curated_events",
        ["stable_key"],
        unique=True,
    )

    # -- event_associations --
    op.add_column(
        "event_associations",
        sa.Column(
            "stable_key",
            sa.String(500),
            nullable=True,
            unique=True,
            comment="Deterministic identity key: source_event + target + types",
        ),
    )
    op.add_column(
        "event_associations",
        sa.Column(
            "source_fingerprint",
            sa.String(64),
            nullable=True,
            comment="MD5 of source data that produced this association",
        ),
    )
    op.add_column(
        "event_associations",
        sa.Column(
            "semantic_fingerprint",
            sa.String(64),
            nullable=True,
            comment="MD5 of semantic content (title+reason+priority+confidence)",
        ),
    )
    op.create_index(
        "ix_event_associations_stable_key",
        "event_associations",
        ["stable_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_event_associations_stable_key", table_name="event_associations")
    op.drop_column("event_associations", "semantic_fingerprint")
    op.drop_column("event_associations", "source_fingerprint")
    op.drop_column("event_associations", "stable_key")

    op.drop_index("ix_curated_events_stable_key", table_name="curated_events")
    op.drop_column("curated_events", "semantic_fingerprint")
    op.drop_column("curated_events", "source_fingerprint")
    op.drop_column("curated_events", "stable_key")
