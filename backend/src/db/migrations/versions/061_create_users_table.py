"""Create users table with JWT authentication support.

Revision ID: 061_create_users_table
Revises: 060_add_hygiene_settings
Create Date: 2026-01-31

Creates the users table with:
- UUID primary key
- family_id (loose, no FK)
- phone/email unique with CHECK constraint
- bcrypt password_hash
- timezone, is_active, timestamps

Seeds a development user for testing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '061_create_users_table'
down_revision = '060_add_hygiene_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('nickname', sa.String(50), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('timezone', sa.String(50), server_default='Asia/Shanghai', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('email'),
        sa.CheckConstraint('phone IS NOT NULL OR email IS NOT NULL', name='ck_users_phone_or_email'),
    )
    op.create_index('idx_users_family', 'users', ['family_id', 'is_active'])

    # Seed development user (only in non-production environments)
    import os
    if os.getenv("ENVIRONMENT", "development") != "production":
        # Password: testpassword123 (bcrypt hash)
        op.execute(sa.text("""
            INSERT INTO users (id, family_id, email, password_hash, username, nickname, timezone)
            VALUES (
                '123e4567-e89b-12d3-a456-426614174001',
                '123e4567-e89b-12d3-a456-426614174000',
                'testuser@example.com',
                '$2b$12$nY1R8KgYaQqW/6MHQL6kG.laEFK6IfdVJxdml9XoDj2rtu/1tSS4S',
                'testuser',
                'Test User',
                'Asia/Shanghai'
            )
            ON CONFLICT DO NOTHING
        """))


def downgrade() -> None:
    op.drop_index('idx_users_family', table_name='users')
    op.drop_table('users')
