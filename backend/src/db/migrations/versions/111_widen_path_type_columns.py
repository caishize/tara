"""Widen path_type column from VARCHAR(10) to VARCHAR(20).

Revision ID: 111
Revises: 110

The 'intervention' path_type (12 chars) exceeds the VARCHAR(10) limit,
causing StringDataRightTruncationError on intervention message inserts.
"""

from alembic import op
from sqlalchemy import inspect, text
import sqlalchemy as sa


revision = "111"
down_revision = "110"


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
    op.alter_column(
        "assistant_chat_messages",
        "path_type",
        type_=sa.String(20),
        existing_type=sa.String(10),
        existing_nullable=True,
    )

    conn = op.get_bind()
    if _table_exists(conn, "tool_executions"):
        op.alter_column(
            "tool_executions",
            "path_type",
            type_=sa.String(20),
            existing_type=sa.String(10),
            existing_nullable=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "tool_executions"):
        op.alter_column(
            "tool_executions",
            "path_type",
            type_=sa.String(10),
            existing_type=sa.String(20),
            existing_nullable=False,
        )

    op.alter_column(
        "assistant_chat_messages",
        "path_type",
        type_=sa.String(10),
        existing_type=sa.String(20),
        existing_nullable=True,
    )
