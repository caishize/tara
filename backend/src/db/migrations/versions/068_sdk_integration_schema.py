"""SDK integration schema - session summaries, tool execution logs, message fields

Revision ID: 068
Revises: 067
Create Date: 2026-02-03

Phase 0 of Claude Agent SDK integration:
- Add archived_at, message_count to assistant_chat_sessions
- Add sequence_number, path_type, tool_calls to assistant_chat_messages
- Create session_summaries table (1:1 with sessions)
- Create tool_execution_logs table (UUID PK, three-layer results)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- assistant_chat_sessions: new columns ---
    op.add_column(
        "assistant_chat_sessions",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "assistant_chat_sessions",
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
    )

    # --- assistant_chat_messages: new columns ---
    op.add_column(
        "assistant_chat_messages",
        sa.Column("sequence_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assistant_chat_messages",
        sa.Column("path_type", sa.String(10), nullable=True),
    )
    op.add_column(
        "assistant_chat_messages",
        sa.Column("tool_calls", JSONB(), nullable=True),
    )

    # --- session_summaries ---
    op.create_table(
        "session_summaries",
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "compressed_up_to",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_session_summaries_user", "session_summaries", ["user_id"]
    )

    # --- tool_execution_logs ---
    op.create_table(
        "tool_execution_logs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assistant_chat_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "path_type",
            sa.String(10),
            nullable=False,
            server_default="slow",
        ),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("arguments", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="running",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_results", JSONB(), nullable=True),
        sa.Column("full_result", JSONB(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "iteration", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_tool_exec_session",
        "tool_execution_logs",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_tool_exec_user",
        "tool_execution_logs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_tool_exec_user_tool",
        "tool_execution_logs",
        ["user_id", "tool_name", "created_at"],
    )

    # --- C2: partial unique index for sequence_number (NULLs excluded) ---
    op.execute(
        "CREATE UNIQUE INDEX ix_chat_messages_session_seq "
        "ON assistant_chat_messages (session_id, sequence_number) "
        "WHERE sequence_number IS NOT NULL"
    )


def downgrade() -> None:
    # --- sequence number index ---
    op.drop_index("ix_chat_messages_session_seq", table_name="assistant_chat_messages")

    # --- tool_execution_logs ---
    op.drop_index("ix_tool_exec_user_tool", table_name="tool_execution_logs")
    op.drop_index("ix_tool_exec_user", table_name="tool_execution_logs")
    op.drop_index("ix_tool_exec_session", table_name="tool_execution_logs")
    op.drop_table("tool_execution_logs")

    # --- session_summaries ---
    op.drop_index("ix_session_summaries_user", table_name="session_summaries")
    op.drop_table("session_summaries")

    # --- assistant_chat_messages: remove columns ---
    op.drop_column("assistant_chat_messages", "tool_calls")
    op.drop_column("assistant_chat_messages", "path_type")
    op.drop_column("assistant_chat_messages", "sequence_number")

    # --- assistant_chat_sessions: remove columns ---
    op.drop_column("assistant_chat_sessions", "message_count")
    op.drop_column("assistant_chat_sessions", "archived_at")
