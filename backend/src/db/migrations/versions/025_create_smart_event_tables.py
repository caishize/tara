"""Create smart event preparation and action log tables

Revision ID: 025
Revises: 024
Create Date: 2025-12-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '025_smart_events'
down_revision = '024_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create event_preparations table
    op.create_table(
        'event_preparations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),  # 'date', 'travel', 'gift', etc.
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Preparation checklist
        sa.Column('checklist', postgresql.JSONB, nullable=False, server_default='[]'),
        # Format: [{id, label, completed, completedAt, linkedType, linkedId}]

        # Linked resources
        sa.Column('gift_recommendation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('shopping_list_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('travel_plan_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Status tracking
        sa.Column('status', sa.String(20), nullable=False, server_default='not_started'),
        # Values: not_started, in_progress, ready, completed

        # User notes
        sa.Column('notes', sa.Text, nullable=True),

        # Wish message (for birthday/anniversary events)
        sa.Column('wish_message', sa.Text, nullable=True),
        sa.Column('wish_sent_at', sa.DateTime, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )

    # Create indexes for event_preparations
    op.create_index('idx_event_prep_family', 'event_preparations', ['family_id'])
    op.create_index('idx_event_prep_event', 'event_preparations', ['event_type', 'event_id'])
    op.create_index('idx_event_prep_status', 'event_preparations', ['status'])

    # Create unique constraint to prevent duplicates
    op.create_unique_constraint(
        'uq_event_prep_event',
        'event_preparations',
        ['family_id', 'event_type', 'event_id']
    )

    # Create event_action_logs table
    op.create_table(
        'event_action_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Action details
        sa.Column('action_type', sa.String(50), nullable=False),
        # Values: view, recommend_gift, select_gift, add_shopping, send_wish, edit, complete_checklist, etc.
        sa.Column('action_data', postgresql.JSONB, nullable=True),

        # Executor
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Result
        sa.Column('result_status', sa.String(20), nullable=True),  # success, failed
        sa.Column('result_data', postgresql.JSONB, nullable=True),

        # Timestamp
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )

    # Create indexes for event_action_logs
    op.create_index('idx_action_log_family', 'event_action_logs', ['family_id'])
    op.create_index('idx_action_log_event', 'event_action_logs', ['event_type', 'event_id'])
    op.create_index('idx_action_log_created', 'event_action_logs', ['created_at'])

    # Create wish_templates table for storing wish message templates
    op.create_table(
        'wish_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=True),  # NULL for system templates

        # Template details
        sa.Column('occasion_type', sa.String(50), nullable=False),  # birthday, anniversary, holiday, etc.
        sa.Column('relationship_type', sa.String(50), nullable=True),  # parent, spouse, friend, etc.
        sa.Column('template_name', sa.String(100), nullable=False),
        sa.Column('template_content', sa.Text, nullable=False),
        sa.Column('tone', sa.String(30), nullable=True),  # formal, casual, warm, humorous

        # Template variables
        sa.Column('variables', postgresql.JSONB, nullable=True),  # [{name, description, example}]

        # Usage tracking
        sa.Column('usage_count', sa.Integer, nullable=False, server_default='0'),

        # Is system template
        sa.Column('is_system', sa.Boolean, nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )

    # Create indexes for wish_templates
    op.create_index('idx_wish_tpl_family', 'wish_templates', ['family_id'])
    op.create_index('idx_wish_tpl_occasion', 'wish_templates', ['occasion_type'])

    # Insert default system wish templates
    op.execute("""
        INSERT INTO wish_templates (occasion_type, relationship_type, template_name, template_content, tone, is_system, variables) VALUES
        ('birthday', 'parent', '父母生日祝福-温馨版', '亲爱的{称呼}，今天是您{age}岁的生日，祝您生日快乐！感谢您多年来的养育之恩，愿您身体健康，笑口常开，幸福安康！', 'warm', true, '[{"name": "称呼", "description": "对父母的称呼", "example": "妈妈"}, {"name": "age", "description": "年龄", "example": "60"}]'),
        ('birthday', 'parent', '父母生日祝福-正式版', '敬爱的{称呼}，值此寿辰之际，祝您福如东海，寿比南山！愿您在新的一岁里，身体康健，万事如意！', 'formal', true, '[{"name": "称呼", "description": "对父母的称呼", "example": "父亲"}]'),
        ('birthday', 'spouse', '爱人生日祝福-浪漫版', '亲爱的{称呼}，今天是你的生日，感谢你走进我的生命。愿我们的爱情像美酒一样，越陈越香。生日快乐，我爱你！', 'warm', true, '[{"name": "称呼", "description": "对爱人的称呼", "example": "老婆"}]'),
        ('birthday', 'child', '孩子生日祝福', '宝贝{称呼}，生日快乐！今天你{age}岁了，愿你健康成长，学业进步，开心每一天！爸爸妈妈永远爱你！', 'warm', true, '[{"name": "称呼", "description": "孩子的名字或昵称", "example": "小明"}, {"name": "age", "description": "年龄", "example": "10"}]'),
        ('birthday', 'friend', '朋友生日祝福', '{称呼}，生日快乐！愿你新的一岁，心想事成，万事顺意！期待下次聚会！', 'casual', true, '[{"name": "称呼", "description": "朋友的称呼", "example": "老王"}]'),
        ('anniversary', 'spouse', '结婚纪念日祝福', '亲爱的{称呼}，今天是我们结婚{years}周年纪念日。感谢你{years}年来的陪伴与包容，愿我们的爱情地久天长！', 'warm', true, '[{"name": "称呼", "description": "爱人的称呼", "example": "老婆"}, {"name": "years", "description": "结婚年数", "example": "10"}]'),
        ('holiday', NULL, '春节祝福', '{称呼}，新年快乐！祝您在新的一年里，身体健康，阖家幸福，万事如意！', 'warm', true, '[{"name": "称呼", "description": "对方的称呼", "example": "王叔叔"}]'),
        ('holiday', NULL, '中秋祝福', '{称呼}，中秋节快乐！月圆人团圆，祝您阖家幸福，事事圆满！', 'warm', true, '[{"name": "称呼", "description": "对方的称呼", "example": "张阿姨"}]')
    """)


def downgrade() -> None:
    op.drop_table('wish_templates')
    op.drop_table('event_action_logs')
    op.drop_table('event_preparations')
