"""create notebook tables

Revision ID: 042_create_notebook_tables
Revises: 041_add_memory_search_indexes
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '042_create_notebook_tables'
down_revision: Union[str, None] = '041_memory_search_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notebooks table
    op.create_table(
        'notebooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), server_default='📚', nullable=True),
        sa.Column('color', sa.String(20), server_default='#6366F1', nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=True),
        sa.Column('source_count', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('chat_history', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('notebook_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for notebooks
    op.create_index('ix_notebooks_user', 'notebooks', ['user_id', 'status'])
    op.create_index('ix_notebooks_created', 'notebooks', ['created_at'])

    # Create notebook_sources table
    op.create_table(
        'notebook_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('notebook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('original_url', sa.Text(), nullable=True),
        sa.Column('original_content', sa.Text(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('notebook_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extraction_status', sa.String(20), server_default='pending', nullable=True),
        sa.Column('extraction_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['notebook_id'], ['notebooks.id'], ondelete='CASCADE')
    )

    # Create indexes for notebook_sources
    op.create_index('ix_notebook_sources_notebook', 'notebook_sources', ['notebook_id'])
    op.create_index('ix_notebook_sources_type', 'notebook_sources', ['type'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_notebook_sources_type', table_name='notebook_sources')
    op.drop_index('ix_notebook_sources_notebook', table_name='notebook_sources')
    op.drop_index('ix_notebooks_created', table_name='notebooks')
    op.drop_index('ix_notebooks_user', table_name='notebooks')

    # Drop tables
    op.drop_table('notebook_sources')
    op.drop_table('notebooks')
