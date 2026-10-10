"""Add status and override_count columns to exclusion_rules.

Revision ID: 098
Revises: 097

Adds status (active/inactive) and override_count fields to support
soft-deactivation and override tracking for exclusion rules.
"""

from alembic import op
import sqlalchemy as sa


revision = "098"
down_revision = "097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exclusion_rules",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active, inactive",
        ),
    )
    op.add_column(
        "exclusion_rules",
        sa.Column(
            "override_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of times the user overrode (bypassed) this rule",
        ),
    )
    op.create_index(
        "ix_exclusion_rules_status",
        "exclusion_rules",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_exclusion_rules_status", table_name="exclusion_rules")
    op.drop_column("exclusion_rules", "override_count")
    op.drop_column("exclusion_rules", "status")
