"""create goals and habits tables

Revision ID: 014_create_goals_habits_tables
Revises: 013_create_housing_tables
Create Date: 2025-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '014_create_goals_habits_tables'
down_revision: Union[str, None] = '013_create_housing_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create goal_status_enum
    op.execute("""
        CREATE TYPE goal_status_enum AS ENUM ('active', 'completed', 'abandoned', 'adjusted')
    """)

    # Create habit_status_enum
    op.execute("""
        CREATE TYPE habit_status_enum AS ENUM ('active', 'paused', 'completed', 'abandoned')
    """)

    # Create goals table
    op.create_table(
        'goals',
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('goal_type', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('target_value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('current_progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('completion_percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('decomposition', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', postgresql.ENUM(name='goal_status_enum', create_type=False), nullable=False, server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('goal_id'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.CheckConstraint('target_value > 0', name='check_goal_target_positive'),
        sa.CheckConstraint('current_progress >= 0', name='check_goal_progress_non_negative'),
        sa.CheckConstraint('completion_percentage >= 0 AND completion_percentage <= 100', name='check_goal_completion_range'),
        sa.CheckConstraint('start_date <= end_date', name='check_goal_date_range'),
    )

    op.create_index('idx_goal_member', 'goals', ['member_id', 'status'])
    op.create_index('idx_goal_family', 'goals', ['family_id', 'status'])
    op.create_index('idx_goal_dates', 'goals', ['start_date', 'end_date'])
    op.create_index('idx_goal_type', 'goals', ['goal_type'])

    # Create goal_progress table
    op.create_table(
        'goal_progress',
        sa.Column('progress_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_date', sa.Date(), nullable=False),
        sa.Column('progress_increment', sa.Float(), nullable=False),
        sa.Column('cumulative_progress', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('progress_id'),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.goal_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.CheckConstraint('progress_increment >= 0', name='check_progress_increment_non_negative'),
        sa.CheckConstraint('cumulative_progress >= 0', name='check_cumulative_progress_non_negative'),
    )

    op.create_index('idx_progress_goal_date', 'goal_progress', ['goal_id', 'record_date'])
    op.create_index('idx_progress_member', 'goal_progress', ['member_id', 'record_date'])
    op.create_index('idx_progress_date', 'goal_progress', ['record_date'])

    # Create habits table
    op.create_table(
        'habits',
        sa.Column('habit_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('habit_description', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('reminder_time', sa.Time(), nullable=False),
        sa.Column('reminder_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_checkins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('milestone_7_achieved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('milestone_21_achieved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('milestone_100_achieved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', postgresql.ENUM(name='habit_status_enum', create_type=False), nullable=False, server_default='active'),
        sa.Column('paused_reason', sa.String(200), nullable=True),
        sa.Column('created_date', sa.Date(), nullable=False),
        sa.Column('last_checkin_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('paused_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('habit_id'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.CheckConstraint('current_streak >= 0', name='check_habit_current_streak'),
        sa.CheckConstraint('longest_streak >= 0', name='check_habit_longest_streak'),
        sa.CheckConstraint('total_checkins >= 0', name='check_habit_total_checkins'),
    )

    op.create_index('idx_habit_member', 'habits', ['member_id', 'status'])
    op.create_index('idx_habit_family', 'habits', ['family_id', 'status'])
    op.create_index('idx_habit_reminder', 'habits', ['reminder_time', 'reminder_enabled'])
    op.create_index('idx_habit_status', 'habits', ['status'])

    # Create habit_checkins table
    op.create_table(
        'habit_checkins',
        sa.Column('checkin_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('habit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('checkin_date', sa.Date(), nullable=False),
        sa.Column('checkin_time', sa.Time(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('streak_days', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('checkin_id'),
        sa.ForeignKeyConstraint(['habit_id'], ['habits.habit_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
    )

    op.create_index('idx_checkin_habit_date', 'habit_checkins', ['habit_id', 'checkin_date'], unique=True)
    op.create_index('idx_checkin_member', 'habit_checkins', ['member_id', 'checkin_date'])
    op.create_index('idx_checkin_date', 'habit_checkins', ['checkin_date'])


def downgrade() -> None:
    op.drop_table('habit_checkins')
    op.drop_table('habits')
    op.drop_table('goal_progress')
    op.drop_table('goals')

    op.execute('DROP TYPE IF EXISTS habit_status_enum')
    op.execute('DROP TYPE IF EXISTS goal_status_enum')
