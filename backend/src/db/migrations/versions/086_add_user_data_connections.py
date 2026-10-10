"""Create user_data_connections table.

Stores OAuth/API connections for external data sources (calendars, email,
smart-home, etc.) linked to user accounts.

Revision ID: 086
Revises: 085
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "086"
down_revision = "085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_data_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        # Provider identification
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("icon_url", sa.String(500), nullable=True),
        # Auth state
        sa.Column(
            "connection_status",
            sa.String(20),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column(
            "auth_type", sa.String(20), nullable=False, server_default="oauth2"
        ),
        # Credentials (AES-256-GCM encrypted JSON blob)
        sa.Column("encrypted_credentials", sa.LargeBinary(), nullable=True),
        sa.Column(
            "scopes",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        # MCP server integration
        sa.Column("mcp_server_url", sa.String(500), nullable=True),
        sa.Column("mcp_server_config", postgresql.JSONB(), nullable=True),
        # Sync state
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "sync_frequency_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Flags / timestamps
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
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

    # Unique: one connection per user per provider
    op.create_unique_constraint(
        "uq_user_provider", "user_data_connections", ["user_id", "provider_name"]
    )

    # Partial index: active connections by user + status
    op.create_index(
        "ix_user_data_connections_user_status",
        "user_data_connections",
        ["user_id", "connection_status"],
        postgresql_where=sa.text("is_active = true"),
    )

    # Family lookup index
    op.create_index(
        "ix_user_data_connections_family",
        "user_data_connections",
        ["family_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_data_connections_family", table_name="user_data_connections"
    )
    op.drop_index(
        "ix_user_data_connections_user_status",
        table_name="user_data_connections",
    )
    op.drop_constraint(
        "uq_user_provider", "user_data_connections", type_="unique"
    )
    op.drop_table("user_data_connections")
