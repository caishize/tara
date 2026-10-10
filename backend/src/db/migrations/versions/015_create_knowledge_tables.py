"""Create knowledge management tables

Revision ID: 015_knowledge
Revises: 014_create_goals_habits_tables
Create Date: 2025-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_knowledge'
down_revision = '014_create_goals_habits_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create knowledge management tables."""

    # Certificates table
    op.create_table(
        'certificates',
        sa.Column('cert_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cert_type', sa.String(50), nullable=False),
        sa.Column('cert_number', sa.Text, nullable=False),
        sa.Column('issue_date', sa.Date, nullable=True),
        sa.Column('expiry_date', sa.Date, nullable=True),
        sa.Column('issuing_authority', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('attachments', postgresql.JSONB, nullable=True),
        sa.Column('reminder_sent', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('reminder_sent_at', sa.TIMESTAMP, nullable=True),
        sa.Column('reminder_days_before', sa.Integer, nullable=False, server_default='365'),
        sa.Column('is_encrypted', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.CheckConstraint('reminder_days_before >= 0 AND reminder_days_before <= 3650', name='check_reminder_days_range'),
    )
    op.create_index('idx_certificate_member', 'certificates', ['member_id', 'is_deleted'])
    op.create_index('idx_certificate_family', 'certificates', ['family_id', 'is_deleted'])
    op.create_index('idx_certificate_expiry', 'certificates', ['expiry_date', 'is_deleted'])
    op.create_index('idx_certificate_type', 'certificates', ['cert_type', 'family_id'])

    # Documents table
    op.create_table(
        'documents',
        sa.Column('doc_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doc_type', sa.String(100), nullable=False),
        sa.Column('doc_title', sa.String(200), nullable=False),
        sa.Column('doc_file_url', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=True),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('ocr_extracted_info', postgresql.JSONB, nullable=True),
        sa.Column('ocr_full_text', sa.Text, nullable=True),
        sa.Column('ocr_confidence', sa.Integer, nullable=True),
        sa.Column('ocr_language', sa.String(10), nullable=True),
        sa.Column('ocr_processed_at', sa.TIMESTAMP, nullable=True),
        sa.Column('auto_classified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('access_level', sa.String(20), nullable=False, server_default='private'),
        sa.Column('is_encrypted', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('checksum', sa.String(64), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.CheckConstraint('ocr_confidence >= 0 AND ocr_confidence <= 100', name='check_ocr_confidence_range'),
        sa.CheckConstraint('file_size >= 0', name='check_file_size_positive'),
        sa.CheckConstraint("access_level IN ('private', 'family_admin', 'shared')", name='check_access_level_enum'),
    )
    op.create_index('idx_document_family', 'documents', ['family_id', 'is_deleted'])
    op.create_index('idx_document_owner', 'documents', ['owner_id', 'is_deleted'])
    op.create_index('idx_document_type', 'documents', ['doc_type', 'family_id'])
    op.create_index('idx_document_checksum', 'documents', ['checksum'])
    op.create_index('idx_document_tags_gin', 'documents', ['tags'], postgresql_using='gin')
    op.create_index('idx_document_ocr_info_gin', 'documents', ['ocr_extracted_info'], postgresql_using='gin')

    # Password Records table
    op.create_table(
        'password_records',
        sa.Column('record_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_name', sa.String(200), nullable=False),
        sa.Column('account_type', sa.String(50), nullable=True),
        sa.Column('account_description', sa.Text, nullable=True),
        sa.Column('last_change_date', sa.Date, nullable=False),
        sa.Column('reminder_cycle_months', sa.Integer, nullable=False, server_default='6'),
        sa.Column('next_reminder_date', sa.Date, nullable=True),
        sa.Column('reminder_sent', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('reminder_sent_at', sa.TIMESTAMP, nullable=True),
        sa.Column('reminder_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.CheckConstraint('reminder_cycle_months IN (0, 1, 3, 6, 12)', name='check_reminder_cycle_valid'),
        sa.CheckConstraint('reminder_count >= 0', name='check_reminder_count_positive'),
    )
    op.create_index('idx_password_record_member', 'password_records', ['member_id', 'is_deleted'])
    op.create_index('idx_password_record_family', 'password_records', ['family_id', 'is_deleted'])
    op.create_index('idx_password_record_next_reminder', 'password_records', ['next_reminder_date', 'is_deleted'])

    # Knowledge Base table
    op.create_table(
        'knowledge_base',
        sa.Column('kb_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False, server_default='note'),
        sa.Column('content_summary', sa.Text, nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('related_module', sa.String(100), nullable=True),
        sa.Column('related_record_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_metadata', postgresql.JSONB, nullable=True),
        sa.Column('vector_embedding', postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('embedding_generated_at', sa.TIMESTAMP, nullable=True),
        sa.Column('relevance_score', sa.Float, nullable=True),
        sa.Column('access_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.TIMESTAMP, nullable=True),
        sa.Column('is_consolidated', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('consolidated_from', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.CheckConstraint("content_type IN ('note', 'article', 'reference', 'fact', 'conversation_extract')", name='check_content_type_enum'),
        sa.CheckConstraint("source IN ('user_added', 'conversation_extract', 'module_linked')", name='check_source_enum'),
        sa.CheckConstraint('relevance_score >= 0.0 AND relevance_score <= 1.0', name='check_relevance_score_range'),
        sa.CheckConstraint('access_count >= 0', name='check_access_count_positive'),
    )
    op.create_index('idx_kb_family', 'knowledge_base', ['family_id', 'is_deleted'])
    op.create_index('idx_kb_author', 'knowledge_base', ['author_id', 'is_deleted'])
    op.create_index('idx_kb_category', 'knowledge_base', ['category', 'family_id'])
    op.create_index('idx_kb_source', 'knowledge_base', ['source', 'family_id'])
    op.create_index('idx_kb_tags_gin', 'knowledge_base', ['tags'], postgresql_using='gin')

    # Notes table
    op.create_table(
        'notes',
        sa.Column('note_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('format', sa.String(20), nullable=False, server_default='plain_text'),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('is_pinned', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('pin_order', sa.Integer, nullable=True),
        sa.Column('is_private', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('color_tag', sa.String(20), nullable=True),
        sa.Column('reminder_date', sa.TIMESTAMP, nullable=True),
        sa.Column('reminder_sent', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.CheckConstraint("format IN ('plain_text', 'markdown')", name='check_note_format_enum'),
    )
    op.create_index('idx_note_family', 'notes', ['family_id', 'is_deleted'])
    op.create_index('idx_note_author', 'notes', ['author_id', 'is_deleted'])
    op.create_index('idx_note_pinned', 'notes', ['is_pinned', 'pin_order', 'family_id'])
    op.create_index('idx_note_tags_gin', 'notes', ['tags'], postgresql_using='gin')


def downgrade():
    """Drop knowledge management tables."""
    op.drop_table('notes')
    op.drop_table('knowledge_base')
    op.drop_table('password_records')
    op.drop_table('documents')
    op.drop_table('certificates')
