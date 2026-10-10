"""create member tables

Revision ID: 001_create_member_tables
Revises:
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_create_member_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Install PostgreSQL extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    # Note: pgvector extension needs to be installed manually: CREATE EXTENSION vector;

    # Create enums
    op.execute("""
        CREATE TYPE gender_enum AS ENUM ('male', 'female', 'other', 'unspecified')
    """)

    op.execute("""
        CREATE TYPE relation_type_enum AS ENUM (
            'spouse', 'parent', 'child', 'sibling',
            'grandparent', 'grandchild', 'uncle_aunt', 'nephew_niece', 'cousin',
            'parent_in_law', 'child_in_law', 'sibling_in_law',
            'friend', 'caregiver', 'other'
        )
    """)

    op.execute("""
        CREATE TYPE session_status_enum AS ENUM ('active', 'completed', 'failed', 'timeout')
    """)

    # Create members table
    op.create_table(
        'members',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('nickname', sa.String(50), nullable=True),
        sa.Column('gender', postgresql.ENUM('male', 'female', 'other', 'unspecified', name='gender_enum', create_type=False), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('id_card', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('occupation', sa.String(100), nullable=True),
        sa.Column('workplace', sa.String(200), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('profile_completion', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('profile_completion >= 0 AND profile_completion <= 100', name='check_profile_completion'),
        sa.CheckConstraint('age >= 0 AND age <= 150', name='check_age_range'),
    )

    op.create_index('idx_member_family', 'members', ['family_id', 'is_deleted'])
    op.create_index('idx_member_phone', 'members', ['phone'], postgresql_where=sa.text('phone IS NOT NULL'))
    op.execute('CREATE INDEX idx_member_name_gin ON members USING gin (name gin_trgm_ops)')

    # Create member_relations table
    op.create_table(
        'member_relations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relation_type', postgresql.ENUM(name='relation_type_enum', create_type=False), nullable=False),
        sa.Column('intimacy_level', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['from_member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_member_id'], ['members.id'], ondelete='CASCADE'),
        sa.CheckConstraint('from_member_id != to_member_id', name='check_no_self_relation'),
        sa.CheckConstraint('intimacy_level >= 1 AND intimacy_level <= 10', name='check_intimacy_range'),
        sa.UniqueConstraint('from_member_id', 'to_member_id', 'relation_type', name='uq_relation'),
    )

    op.create_index('idx_relation_from', 'member_relations', ['from_member_id', 'relation_type'])
    op.create_index('idx_relation_to', 'member_relations', ['to_member_id', 'relation_type'])
    op.create_index('idx_relation_family', 'member_relations', ['family_id'])

    # Create member_profiles table
    op.create_table(
        'member_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('preferences', postgresql.JSONB(), nullable=True),
        sa.Column('habits', postgresql.JSONB(), nullable=True),
        sa.Column('health_summary', sa.Text(), nullable=True),
        sa.Column('personality_traits', postgresql.JSONB(), nullable=True),
        sa.Column('special_notes', sa.Text(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float(), dimensions=1), nullable=True),
        sa.Column('last_enriched_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('member_id', name='uq_member_profile'),
    )

    op.create_index('idx_profile_preferences_gin', 'member_profiles', ['preferences'], postgresql_using='gin')

    # Create conversation_sessions table
    op.create_table(
        'conversation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('intent', sa.String(50), nullable=True),
        sa.Column('slots', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('context', postgresql.JSONB(), nullable=True),
        sa.Column('status', postgresql.ENUM(name='session_status_enum', create_type=False), nullable=False, server_default='active'),
        sa.Column('started_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_activity_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('timeout_at', sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('timeout_at > started_at', name='check_timeout_after_start'),
        sa.CheckConstraint('completed_at IS NULL OR completed_at >= started_at', name='check_completed_after_start'),
    )

    op.create_index('idx_session_user', 'conversation_sessions', ['user_id', 'status', 'started_at'])
    op.create_index('idx_session_timeout', 'conversation_sessions', ['timeout_at'],
                    postgresql_where=sa.text("status = 'active'"))


def downgrade() -> None:
    op.drop_table('conversation_sessions')
    op.drop_table('member_profiles')
    op.drop_table('member_relations')
    op.drop_table('members')

    op.execute('DROP TYPE IF EXISTS session_status_enum')
    op.execute('DROP TYPE IF EXISTS relation_type_enum')
    op.execute('DROP TYPE IF EXISTS gender_enum')
