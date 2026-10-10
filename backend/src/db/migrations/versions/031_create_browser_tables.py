"""Create AI Native Browser tables

Revision ID: 031
Revises: 030
Create Date: 2025-12-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '031_browser_tables'
down_revision = '030_member_loc_vehicle_drv'
branch_labels = None
depends_on = None


def table_exists(connection, table_name):
    """Check if a table exists in the database."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = '{table_name}')"
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Browser Sessions table
    if not table_exists(connection, 'browser_sessions'):
        op.create_table(
            'browser_sessions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('created_by', UUID(as_uuid=True), nullable=False),
            sa.Column('session_name', sa.String(200), nullable=False),
            sa.Column('purpose', sa.Text),
            sa.Column('website_domain', sa.String(255)),
            sa.Column('platform', sa.String(50)),  # jd, taobao, tmall, pdd, etc.
            sa.Column('status', sa.String(20), nullable=False, server_default='active'),  # active, paused, closed, error
            sa.Column('ai_control_enabled', sa.Boolean, server_default='false'),
            sa.Column('ai_auto_approve_safe_ops', sa.Boolean, server_default='true'),
            sa.Column('current_url', sa.Text),
            sa.Column('current_title', sa.String(500)),
            sa.Column('viewport_width', sa.Integer, server_default='1280'),
            sa.Column('viewport_height', sa.Integer, server_default='720'),
            sa.Column('user_agent', sa.Text),
            sa.Column('operation_count', sa.Integer, server_default='0'),
            sa.Column('last_activity_at', sa.DateTime),
            sa.Column('closed_at', sa.DateTime),
            sa.Column('error_message', sa.Text),
            sa.Column('is_deleted', sa.Boolean, server_default='false'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_browser_sessions_family_status', 'browser_sessions', ['family_id', 'status'])

    # Browser Operation Logs table
    if not table_exists(connection, 'browser_operation_logs'):
        op.create_table(
            'browser_operation_logs',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('browser_sessions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('operation_type', sa.String(50), nullable=False),  # navigate, click, type, extract, etc.
            sa.Column('operation_params', JSONB),
            sa.Column('risk_level', sa.String(20), nullable=False),  # safe, low, medium, high, critical
            sa.Column('executed_by', UUID(as_uuid=True), nullable=False),
            sa.Column('success', sa.Boolean, nullable=False),
            sa.Column('ai_initiated', sa.Boolean, server_default='false'),
            sa.Column('user_confirmed', sa.Boolean, server_default='false'),
            sa.Column('confirmation_method', sa.String(50)),  # auto, notification, websocket, dialog
            sa.Column('result_data', JSONB),
            sa.Column('error_message', sa.Text),
            sa.Column('error_type', sa.String(100)),
            sa.Column('screenshot_path', sa.String(500)),
            sa.Column('execution_time_ms', sa.Integer),
            sa.Column('url_before', sa.Text),
            sa.Column('url_after', sa.Text),
            sa.Column('page_title', sa.String(500)),
            sa.Column('correlation_id', sa.String(50)),
            sa.Column('executed_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_browser_ops_session', 'browser_operation_logs', ['session_id', 'executed_at'])
        op.create_index('ix_browser_ops_type', 'browser_operation_logs', ['operation_type'])
        op.create_index('ix_browser_ops_ai', 'browser_operation_logs', ['ai_initiated'])

    # Browser Credentials table (encrypted cookie storage)
    if not table_exists(connection, 'browser_credentials'):
        op.create_table(
            'browser_credentials',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('browser_sessions.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('encrypted_cookies', sa.Text),  # Fernet encrypted JSON
            sa.Column('encrypted_storage', sa.Text),  # Fernet encrypted JSON (localStorage, sessionStorage)
            sa.Column('last_url', sa.Text),
            sa.Column('encryption_key_id', sa.String(100)),  # For key rotation
            sa.Column('expires_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_browser_creds_session', 'browser_credentials', ['session_id'])


def downgrade():
    op.drop_table('browser_credentials')
    op.drop_table('browser_operation_logs')
    op.drop_table('browser_sessions')
