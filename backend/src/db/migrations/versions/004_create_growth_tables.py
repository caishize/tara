"""Create growth tables

Revision ID: 004_create_growth_tables
Revises: 003_create_gift_tables
Create Date: 2025-11-24 09:50:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers
revision = '004_create_growth_tables'
down_revision = '003_create_gift_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    milestone_category_enum = sa.Enum(
        'LANGUAGE', 'MOTOR', 'SOCIAL', 'COGNITIVE', 'SELF_CARE',
        name='milestone_category_enum'
    )
    milestone_category_enum.create(op.get_bind())

    resource_type_enum = sa.Enum(
        'BOOK', 'TOY', 'MUSIC', 'COURSE', 'APP', 'VIDEO',
        name='resource_type_enum'
    )
    resource_type_enum.create(op.get_bind())

    resource_category_enum = sa.Enum(
        'LANGUAGE_DEVELOPMENT', 'MOTOR_SKILLS', 'COGNITIVE', 'SOCIAL_EMOTIONAL',
        'CREATIVITY', 'SCIENCE', 'MATH', 'READING',
        name='resource_category_enum'
    )
    resource_category_enum.create(op.get_bind())

    interest_class_type_enum = sa.Enum(
        'SPORTS', 'MUSIC', 'ART', 'LANGUAGE', 'STEM', 'DANCE', 'OTHER',
        name='interest_class_type_enum'
    )
    interest_class_type_enum.create(op.get_bind())

    # child_growth_profiles table
    op.create_table(
        'child_growth_profiles',
        sa.Column('profile_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('birth_date', sa.Date, nullable=False),
        sa.Column('gender', sa.String(10), nullable=False),  # male/female
        sa.Column('birth_height_cm', sa.Float, nullable=True),
        sa.Column('birth_weight_kg', sa.Float, nullable=True),
        sa.Column('birth_head_circumference_cm', sa.Float, nullable=True),
        sa.Column('age_group_template', sa.String(20), nullable=False),  # infant/preschool/school_age
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['member_id'], ['members.member_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['families.family_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_growth_profiles_member_id', 'child_growth_profiles', ['member_id'])
    op.create_index('ix_growth_profiles_family_id', 'child_growth_profiles', ['family_id'])

    # growth_records table
    op.create_table(
        'growth_records',
        sa.Column('record_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('profile_id', UUID(as_uuid=True), nullable=False),
        sa.Column('measured_date', sa.Date, nullable=False),
        sa.Column('height_cm', sa.Float, nullable=True),  # CONFIDENTIAL - encrypted
        sa.Column('weight_kg', sa.Float, nullable=True),  # CONFIDENTIAL - encrypted
        sa.Column('head_circumference_cm', sa.Float, nullable=True),  # CONFIDENTIAL - encrypted
        sa.Column('bmi', sa.Float, nullable=True),
        sa.Column('who_height_percentile', sa.Float, nullable=True),
        sa.Column('who_weight_percentile', sa.Float, nullable=True),
        sa.Column('anomaly_detected', sa.Boolean, nullable=False, default=False),
        sa.Column('anomaly_type', sa.String(50), nullable=True),  # growth_too_fast/growth_too_slow/growth_stagnant
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['profile_id'], ['child_growth_profiles.profile_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_growth_records_profile_id', 'growth_records', ['profile_id'])
    op.create_index('ix_growth_records_measured_date', 'growth_records', ['measured_date'])

    # milestones table
    op.create_table(
        'milestones',
        sa.Column('milestone_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('profile_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_name', sa.String(200), nullable=False),  # RESTRICTED - encrypted
        sa.Column('category', milestone_category_enum, nullable=False),
        sa.Column('achieved_date', sa.Date, nullable=False),
        sa.Column('age_in_months', sa.Integer, nullable=False),
        sa.Column('description', sa.Text, nullable=True),  # RESTRICTED - encrypted
        sa.Column('photos', ARRAY(sa.String), nullable=True),  # RESTRICTED - encrypted URLs
        sa.Column('matched_standard_milestone', sa.String(200), nullable=True),
        sa.Column('is_early', sa.Boolean, nullable=True),
        sa.Column('is_late', sa.Boolean, nullable=True),
        sa.Column('standard_age_range_months', sa.String(50), nullable=True),  # e.g., "12-15"
        sa.Column('llm_confidence', sa.Float, nullable=True),
        sa.Column('significance_score', sa.Integer, nullable=True),  # 1-5
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['profile_id'], ['child_growth_profiles.profile_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_milestones_profile_id', 'milestones', ['profile_id'])
    op.create_index('ix_milestones_category', 'milestones', ['category'])
    op.create_index('ix_milestones_achieved_date', 'milestones', ['achieved_date'])

    # education_resources table
    op.create_table(
        'education_resources',
        sa.Column('resource_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('resource_type', resource_type_enum, nullable=False),
        sa.Column('category', resource_category_enum, nullable=False),
        sa.Column('age_range_months', sa.String(50), nullable=False),  # e.g., "24-36"
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('purchase_link', sa.String(500), nullable=True),
        sa.Column('price_range', sa.String(50), nullable=True),
        sa.Column('rating', sa.Float, nullable=True),
        sa.Column('embedding_vector', ARRAY(sa.Float), nullable=True),  # For vector search
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
    )
    op.create_index('ix_education_resources_type', 'education_resources', ['resource_type'])
    op.create_index('ix_education_resources_category', 'education_resources', ['category'])

    # interest_classes table
    op.create_table(
        'interest_classes',
        sa.Column('class_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('profile_id', UUID(as_uuid=True), nullable=False),
        sa.Column('class_name', sa.String(200), nullable=False),
        sa.Column('class_type', interest_class_type_enum, nullable=False),
        sa.Column('schedule', JSONB, nullable=False),  # {day: "Monday", time: "17:00", duration_minutes: 60}
        sa.Column('location', sa.String(300), nullable=True),
        sa.Column('instructor', sa.String(100), nullable=True),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=True),
        sa.Column('total_sessions', sa.Integer, nullable=False),
        sa.Column('attended_sessions', sa.Integer, nullable=False, default=0),
        sa.Column('attendance_rate', sa.Float, nullable=True),
        sa.Column('total_fee', sa.Float, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_current', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['profile_id'], ['child_growth_profiles.profile_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_interest_classes_profile_id', 'interest_classes', ['profile_id'])
    op.create_index('ix_interest_classes_is_current', 'interest_classes', ['is_current'])


def downgrade() -> None:
    op.drop_table('interest_classes')
    op.drop_table('education_resources')
    op.drop_table('milestones')
    op.drop_table('growth_records')
    op.drop_table('child_growth_profiles')

    # Drop enums
    sa.Enum(name='interest_class_type_enum').drop(op.get_bind())
    sa.Enum(name='resource_category_enum').drop(op.get_bind())
    sa.Enum(name='resource_type_enum').drop(op.get_bind())
    sa.Enum(name='milestone_category_enum').drop(op.get_bind())
