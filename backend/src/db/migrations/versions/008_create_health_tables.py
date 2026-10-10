"""Health tables"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '008'
down_revision = '006_create_relationship_tables'

def upgrade():
    # Health Profiles table
    op.create_table('health_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('blood_type', sa.String(10), nullable=True),
        sa.Column('allergies', JSONB, nullable=True),
        sa.Column('chronic_diseases', JSONB, nullable=True),
        sa.Column('genetic_conditions', JSONB, nullable=True),
        sa.Column('emergency_contact', JSONB, nullable=True),
        sa.Column('medical_insurance', JSONB, nullable=True),
        sa.Column('additional_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_health_profiles_member_id', 'health_profiles', ['member_id'])

    # Health Records table
    op.create_table('health_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='CASCADE'), nullable=False),
        sa.Column('record_type', sa.String(50), nullable=False),
        sa.Column('record_date', sa.Date, nullable=False),
        sa.Column('diagnosis', sa.String(500), nullable=True),
        sa.Column('symptoms', JSONB, nullable=True),
        sa.Column('treatment', sa.String(1000), nullable=True),
        sa.Column('medications', JSONB, nullable=True),
        sa.Column('test_results', JSONB, nullable=True),
        sa.Column('doctor_name', sa.String(100), nullable=True),
        sa.Column('hospital', sa.String(200), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('doctor_notes', sa.Text, nullable=True),
        sa.Column('patient_notes', sa.Text, nullable=True),
        sa.Column('severity', sa.String(20), nullable=True, server_default='routine'),
        sa.Column('follow_up_required', sa.Boolean, nullable=True, server_default='false'),
        sa.Column('follow_up_date', sa.Date, nullable=True),
        sa.Column('attachments', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_health_records_member_id', 'health_records', ['member_id'])
    op.create_index('ix_health_records_record_date', 'health_records', ['record_date'])

    # Health Goals table
    op.create_table('health_goals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_type', sa.String(50), nullable=False),
        sa.Column('target_value', sa.String(100), nullable=False),
        sa.Column('current_value', sa.String(100), nullable=True),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('execution_plan', JSONB, nullable=True),
        sa.Column('progress_percentage', sa.Float, nullable=True, default=0.0),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_health_goals_member_id', 'health_goals', ['member_id'])
    op.create_index('ix_health_goals_status', 'health_goals', ['status'])

    # Checkup Reports table
    op.create_table('checkup_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='CASCADE'), nullable=False),
        sa.Column('checkup_date', sa.Date, nullable=False),
        sa.Column('checkup_type', sa.String(100), nullable=True),
        sa.Column('hospital', sa.String(200), nullable=True),
        sa.Column('doctor', sa.String(100), nullable=True),
        sa.Column('report_summary', sa.Text, nullable=True),
        sa.Column('key_indicators', JSONB, nullable=True),
        sa.Column('abnormal_findings', JSONB, nullable=True),
        sa.Column('recommendations', JSONB, nullable=True),
        sa.Column('report_files', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_checkup_reports_member_id', 'checkup_reports', ['member_id'])
    op.create_index('ix_checkup_reports_checkup_date', 'checkup_reports', ['checkup_date'])

    # Medications table
    op.create_table('medications',
        sa.Column('medication_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='CASCADE')),
        sa.Column('name', sa.String(200)),
        sa.Column('dosage', sa.String(100)),
        sa.Column('frequency', sa.String(50)),
        sa.Column('start_date', sa.Date),
        sa.Column('end_date', sa.Date),
        sa.Column('inventory', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_medications_member_id', 'medications', ['member_id'])

    # Vital Signs table
    op.create_table('vital_signs',
        sa.Column('record_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='CASCADE')),
        sa.Column('measured_date', sa.Date),
        sa.Column('blood_pressure_systolic', sa.Integer),
        sa.Column('blood_pressure_diastolic', sa.Integer),
        sa.Column('heart_rate', sa.Integer),
        sa.Column('temperature', sa.Float),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_vital_signs_member_id', 'vital_signs', ['member_id'])

def downgrade():
    op.drop_index('ix_vital_signs_member_id')
    op.drop_table('vital_signs')
    op.drop_index('ix_medications_member_id')
    op.drop_table('medications')
    op.drop_index('ix_checkup_reports_checkup_date')
    op.drop_index('ix_checkup_reports_member_id')
    op.drop_table('checkup_reports')
    op.drop_index('ix_health_goals_status')
    op.drop_index('ix_health_goals_member_id')
    op.drop_table('health_goals')
    op.drop_index('ix_health_records_record_date')
    op.drop_index('ix_health_records_member_id')
    op.drop_table('health_records')
    op.drop_index('ix_health_profiles_member_id')
    op.drop_table('health_profiles')
