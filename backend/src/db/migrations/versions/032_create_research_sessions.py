"""Create research_sessions table for Fast Research functionality

Revision ID: 032_create_research_sessions
Revises: 031_create_browser_tables
Create Date: 2024-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '032_research_sessions'
down_revision = '031_browser_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create research_sessions table."""
    op.create_table(
        'research_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('topic', sa.String(500), nullable=False),
        sa.Column('scenario', sa.String(50), server_default='general'),
        sa.Column('status', sa.String(50), server_default='ready'),
        sa.Column('candidates', postgresql.JSONB(), server_default='[]'),
        sa.Column('manual_items', postgresql.JSONB(), server_default='[]'),
        sa.Column('selected_ids', postgresql.JSONB(), server_default='[]'),
        sa.Column('synthesis', postgresql.JSONB(), nullable=True),
        sa.Column('search_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index(
        'ix_research_sessions_user',
        'research_sessions',
        ['user_id', 'status']
    )
    op.create_index(
        'ix_research_sessions_created',
        'research_sessions',
        ['created_at']
    )


def downgrade() -> None:
    """Drop research_sessions table."""
    op.drop_index('ix_research_sessions_created', table_name='research_sessions')
    op.drop_index('ix_research_sessions_user', table_name='research_sessions')
    op.drop_table('research_sessions')
