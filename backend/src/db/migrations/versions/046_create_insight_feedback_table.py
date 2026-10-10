"""Create insight feedback table

Revision ID: 046_insight_feedback
Revises: 045_embedding_feedback
Create Date: 2026-01-21

Creates the insight_feedbacks table for user feedback learning.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '046_insight_feedback'
down_revision = '045_embedding_feedback'
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

    # Create insight_feedbacks table
    if not table_exists(connection, 'insight_feedbacks'):
        op.create_table(
            'insight_feedbacks',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),

            # The insight this feedback is for
            sa.Column('insight_id', UUID(as_uuid=True), nullable=False),

            # Feedback details
            sa.Column('feedback_type', sa.String(30), nullable=False),
            sa.Column('comment', sa.Text, nullable=True),

            # The source memory (for updating weights)
            sa.Column('source_memory_id', UUID(as_uuid=True), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),

            # Foreign keys
            sa.ForeignKeyConstraint(['insight_id'], ['memory_insights.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['source_memory_id'], ['conversation_memories.id'], ondelete='SET NULL'),
        )

        # Create indexes
        op.create_index('ix_insight_feedback_user', 'insight_feedbacks', ['user_id'])
        op.create_index('ix_insight_feedback_insight', 'insight_feedbacks', ['insight_id'])
        op.create_index('ix_insight_feedback_type', 'insight_feedbacks', ['feedback_type'])


def downgrade():
    op.drop_table('insight_feedbacks')
