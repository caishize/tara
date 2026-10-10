"""Add intelligent secretary tables

Revision ID: 029
Revises: 028
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '029_intelligent_secretary'
down_revision = '028_job_executions'
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

    # 对话会话表
    if not table_exists(connection, 'conversation_sessions'):
        op.create_table(
            'conversation_sessions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), sa.ForeignKey('families.id', ondelete='CASCADE'), nullable=False),
            sa.Column('title', sa.String(200)),
            sa.Column('started_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('last_active_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('context', JSONB),
            sa.Column('status', sa.String(20), server_default='active'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_conversation_sessions_user', 'conversation_sessions', ['user_id', 'status'])
        op.create_index('ix_conversation_sessions_family', 'conversation_sessions', ['family_id'])

    # 对话消息表
    if not table_exists(connection, 'conversation_messages'):
        op.create_table(
            'conversation_messages',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('conversation_sessions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('role', sa.String(20), nullable=False),  # user, assistant, system
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('intent', sa.String(50)),
            sa.Column('entities', JSONB),
            sa.Column('metadata', JSONB),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_conversation_messages_session', 'conversation_messages', ['session_id', 'created_at'])

    # 今日待办聚合表 (缓存表)
    if not table_exists(connection, 'today_items'):
        op.create_table(
            'today_items',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),  # FK removed for flexibility
            sa.Column('user_id', UUID(as_uuid=True)),  # FK removed for flexibility
            sa.Column('source_type', sa.String(50), nullable=False),  # date, task, health, shopping, etc.
            sa.Column('source_id', UUID(as_uuid=True), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('description', sa.Text),
            sa.Column('urgency', sa.String(20), nullable=False),  # urgent, today, upcoming
            sa.Column('due_datetime', sa.DateTime),
            sa.Column('actions', JSONB),  # [{type, label, url}]
            sa.Column('status', sa.String(20), server_default='pending'),
            sa.Column('completed_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_today_items_family_status', 'today_items', ['family_id', 'status', 'urgency'])
        op.create_index('ix_today_items_user', 'today_items', ['user_id', 'status'])

    # 准备方案表
    if not table_exists(connection, 'preparation_plans'):
        op.create_table(
            'preparation_plans',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('event_type', sa.String(50), nullable=False),  # birthday, anniversary, holiday
            sa.Column('event_id', UUID(as_uuid=True), nullable=False),
            sa.Column('event_date', sa.Date, nullable=False),
            sa.Column('member_id', UUID(as_uuid=True)),  # FK removed
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('plan_content', JSONB, nullable=False),  # {gift_options, cake_options, restaurant_options, wishes, schedule}
            sa.Column('status', sa.String(20), server_default='draft'),  # draft, sent, adopted, completed
            sa.Column('adopted_selections', JSONB),  # User's selections when adopting
            sa.Column('adopted_at', sa.DateTime),
            sa.Column('notified_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_preparation_plans_family_event', 'preparation_plans', ['family_id', 'event_type', 'event_id'])
        op.create_index('ix_preparation_plans_status', 'preparation_plans', ['status', 'event_date'])

    # 准备任务表
    if not table_exists(connection, 'preparation_tasks'):
        op.create_table(
            'preparation_tasks',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('plan_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('task_type', sa.String(50)),  # gift, cake, restaurant, decoration, etc.
            sa.Column('assignee_id', UUID(as_uuid=True)),  # FK removed
            sa.Column('due_date', sa.Date),
            sa.Column('status', sa.String(20), server_default='pending'),
            sa.Column('completed_at', sa.DateTime),
            sa.Column('metadata', JSONB),  # Additional task-specific data
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_preparation_tasks_plan', 'preparation_tasks', ['plan_id', 'status'])

    # 智能提醒表
    if not table_exists(connection, 'smart_reminders'):
        op.create_table(
            'smart_reminders',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('source_type', sa.String(50), nullable=False),
            sa.Column('source_id', UUID(as_uuid=True), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('urgency_level', sa.String(20), nullable=False),  # urgent, important, normal, low
            sa.Column('preferred_time', sa.Time),
            sa.Column('retry_count', sa.Integer, server_default='0'),
            sa.Column('max_retries', sa.Integer, server_default='3'),
            sa.Column('last_sent_at', sa.DateTime),
            sa.Column('next_send_at', sa.DateTime),
            sa.Column('acknowledged_at', sa.DateTime),
            sa.Column('status', sa.String(20), server_default='pending'),  # pending, sent, acknowledged, snoozed, cancelled
            sa.Column('strategy', JSONB),  # Reminder strategy configuration
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_smart_reminders_next_send', 'smart_reminders', ['next_send_at', 'status'])
        op.create_index('ix_smart_reminders_user', 'smart_reminders', ['user_id', 'status'])

    # 用户活跃模式表
    if not table_exists(connection, 'user_activity_patterns'):
        op.create_table(
            'user_activity_patterns',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False, unique=True),  # FK removed
            sa.Column('weekday_active_hours', JSONB),  # [8, 9, 12, 13, 18, 19, 20, 21]
            sa.Column('weekend_active_hours', JSONB),
            sa.Column('preferred_reminder_times', JSONB),  # {morning: "08:00", evening: "20:00"}
            sa.Column('busy_patterns', JSONB),  # Detected busy time patterns
            sa.Column('response_rate', sa.Float),  # Historical response rate
            sa.Column('avg_response_time_minutes', sa.Integer),
            sa.Column('last_analyzed_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    # 中国节日方案表
    if not table_exists(connection, 'chinese_holiday_plans'):
        op.create_table(
            'chinese_holiday_plans',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('holiday_type', sa.String(50), nullable=False),  # spring_festival, mid_autumn, qingming, dragon_boat, etc.
            sa.Column('holiday_year', sa.Integer, nullable=False),
            sa.Column('holiday_date', sa.Date, nullable=False),
            sa.Column('plan_content', JSONB, nullable=False),  # {red_envelopes, shopping_list, visit_schedule, dinner_menu, etc.}
            sa.Column('region', sa.String(50)),  # north, south, etc.
            sa.Column('status', sa.String(20), server_default='draft'),
            sa.Column('adopted_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_chinese_holiday_plans_family', 'chinese_holiday_plans', ['family_id', 'holiday_type', 'holiday_year'])

    # 家庭协作任务表
    if not table_exists(connection, 'family_tasks'):
        op.create_table(
            'family_tasks',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('parent_task_id', UUID(as_uuid=True)),  # FK removed
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('description', sa.Text),
            sa.Column('task_type', sa.String(50)),  # preparation, shopping, routine, etc.
            sa.Column('creator_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('assignee_id', UUID(as_uuid=True)),  # FK removed
            sa.Column('due_date', sa.Date),
            sa.Column('due_time', sa.Time),
            sa.Column('priority', sa.String(20), server_default='normal'),  # low, normal, high, urgent
            sa.Column('status', sa.String(20), server_default='pending'),  # pending, in_progress, completed, cancelled
            sa.Column('completed_at', sa.DateTime),
            sa.Column('metadata', JSONB),  # Additional task data
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index('ix_family_tasks_assignee', 'family_tasks', ['assignee_id', 'status'])
        op.create_index('ix_family_tasks_family', 'family_tasks', ['family_id', 'status'])
        op.create_index('ix_family_tasks_parent', 'family_tasks', ['parent_task_id'])
        op.create_index('ix_family_tasks_due', 'family_tasks', ['due_date', 'status'])

    # AI建议表 (缓存AI生成的建议)
    if not table_exists(connection, 'ai_suggestions'):
        op.create_table(
            'ai_suggestions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),  # FK removed
            sa.Column('user_id', UUID(as_uuid=True)),  # FK removed
            sa.Column('suggestion_type', sa.String(50), nullable=False),  # weekend_planning, birthday_prep, shopping_deal, etc.
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('actions', JSONB),  # [{type, label, url}]
            sa.Column('context', JSONB),  # Context that generated this suggestion
            sa.Column('priority', sa.Integer, server_default='0'),  # Higher = more important
            sa.Column('valid_until', sa.DateTime),
            sa.Column('dismissed_at', sa.DateTime),
            sa.Column('acted_upon_at', sa.DateTime),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_ai_suggestions_family', 'ai_suggestions', ['family_id', 'created_at'])


def downgrade():
    op.drop_table('ai_suggestions')
    op.drop_table('family_tasks')
    op.drop_table('chinese_holiday_plans')
    op.drop_table('user_activity_patterns')
    op.drop_table('smart_reminders')
    op.drop_table('preparation_tasks')
    op.drop_table('preparation_plans')
    op.drop_table('today_items')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_sessions')
