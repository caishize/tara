"""Add professional relations and work history

Revision ID: 047_professional_relations
Revises: 046_insight_feedback
Create Date: 2026-01-23

Creates:
- professional_relation_type_enum enum type
- work_histories table for member work experience
- professional_relations table for professional relationships
- Adds current_company and current_position to members table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '047_professional_relations'
down_revision = '046_insight_feedback'
branch_labels = None
depends_on = None


def table_exists(connection, table_name):
    """Check if a table exists in the database."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = '{table_name}')"
    ))
    return result.scalar()


def column_exists(connection, table_name, column_name):
    """Check if a column exists in a table."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}')"
    ))
    return result.scalar()


def enum_exists(connection, enum_name):
    """Check if an enum type exists in the database."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}')"
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Create professional_relation_type_enum enum
    if not enum_exists(connection, 'professional_relation_type_enum'):
        op.execute("""
            CREATE TYPE professional_relation_type_enum AS ENUM (
                'boss', 'subordinate', 'peer', 'mentor', 'mentee',
                'client', 'vendor', 'partner', 'other'
            )
        """)

    # Add current_company and current_position to members table
    if not column_exists(connection, 'members', 'current_company'):
        op.add_column('members', sa.Column('current_company', sa.String(200), nullable=True))

    if not column_exists(connection, 'members', 'current_position'):
        op.add_column('members', sa.Column('current_position', sa.String(100), nullable=True))

    # Create work_histories table
    if not table_exists(connection, 'work_histories'):
        op.create_table(
            'work_histories',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),
            sa.Column('member_id', UUID(as_uuid=True), nullable=False),

            # Work Info
            sa.Column('company_name', sa.String(200), nullable=False),
            sa.Column('position', sa.String(100), nullable=True),
            sa.Column('department', sa.String(100), nullable=True),

            # Time Period
            sa.Column('start_date', sa.Date, nullable=True),
            sa.Column('end_date', sa.Date, nullable=True),
            sa.Column('is_current', sa.Boolean, nullable=False, server_default='false'),

            # Additional Info
            sa.Column('notes', sa.Text, nullable=True),

            # Metadata
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),

            # Foreign Keys
            sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('idx_work_history_member', 'work_histories', ['member_id'])
        op.create_index('idx_work_history_family', 'work_histories', ['family_id'])
        op.create_index('idx_work_history_company', 'work_histories', ['company_name'])
        op.create_index('idx_work_history_current', 'work_histories', ['member_id', 'is_current'])

    # Create professional_relations table
    if not table_exists(connection, 'professional_relations'):
        op.create_table(
            'professional_relations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),
            sa.Column('from_member_id', UUID(as_uuid=True), nullable=False),
            sa.Column('to_member_id', UUID(as_uuid=True), nullable=False),

            # Relation Info
            sa.Column('relation_type', sa.Enum(
                'boss', 'subordinate', 'peer', 'mentor', 'mentee',
                'client', 'vendor', 'partner', 'other',
                name='professional_relation_type_enum',
                create_type=False
            ), nullable=False),
            sa.Column('company_name', sa.String(200), nullable=True),

            # Time Period
            sa.Column('start_date', sa.Date, nullable=True),
            sa.Column('end_date', sa.Date, nullable=True),
            sa.Column('is_current', sa.Boolean, nullable=False, server_default='true'),

            # Additional Info
            sa.Column('notes', sa.Text, nullable=True),

            # Metadata
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),

            # Foreign Keys
            sa.ForeignKeyConstraint(['from_member_id'], ['members.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['to_member_id'], ['members.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('idx_prof_rel_from_member', 'professional_relations', ['from_member_id'])
        op.create_index('idx_prof_rel_to_member', 'professional_relations', ['to_member_id'])
        op.create_index('idx_prof_rel_family', 'professional_relations', ['family_id'])
        op.create_index('idx_prof_rel_company', 'professional_relations', ['company_name'])
        op.create_index('idx_prof_rel_type', 'professional_relations', ['relation_type'])
        op.create_index('idx_prof_rel_current', 'professional_relations', ['from_member_id', 'is_current'])


def downgrade():
    # Drop professional_relations table
    op.drop_table('professional_relations')

    # Drop work_histories table
    op.drop_table('work_histories')

    # Remove columns from members table
    op.drop_column('members', 'current_position')
    op.drop_column('members', 'current_company')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS professional_relation_type_enum')
