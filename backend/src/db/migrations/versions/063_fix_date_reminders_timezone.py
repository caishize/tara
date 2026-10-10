"""fix date_reminders datetime columns to use timezone

Revision ID: 063_fix_date_reminders_timezone
Revises: 062_create_hygiene_run_logs
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa

revision = "063_fix_date_reminders_timezone"
down_revision = "062_create_hygiene_run_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "date_reminders",
        "reminder_time",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="reminder_time AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "date_reminders",
        "actual_sent_time",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="actual_sent_time AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "date_reminders",
        "clicked_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="clicked_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "date_reminders",
        "reminder_time",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "date_reminders",
        "actual_sent_time",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "date_reminders",
        "clicked_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
