"""Create relationship tables

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '006_create_relationship_tables'
down_revision = '005_create_finance_tables'

def upgrade():
    op.execute("""
        CREATE TYPE contact_type_enum AS ENUM ('FAMILY', 'FRIEND', 'COLLEAGUE', 'OTHER');
        CREATE TYPE relation_type_enum AS ENUM ('PARENT', 'SIBLING', 'FRIEND', 'COLLEAGUE');
        CREATE TYPE interaction_type_enum AS ENUM ('MEETING', 'CALL', 'MESSAGE', 'GIFT', 'FAVOR');
    """)
    
    op.create_table('contacts',
        sa.Column('contact_id', UUID, primary_key=True),
        sa.Column('family_id', UUID, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('contact_type', sa.String(20)),
        sa.Column('phone', sa.String(50)),  # CONFIDENTIAL
        sa.Column('email', sa.String(100)), # CONFIDENTIAL
        sa.Column('wechat_id', sa.String(100)),
        sa.Column('importance_level', sa.Integer, default=3),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    
    op.create_table('favor_records',
        sa.Column('favor_id', UUID, primary_key=True),
        sa.Column('family_id', UUID, nullable=False),
        sa.Column('contact_id', UUID, nullable=False),
        sa.Column('favor_type', sa.String(20)),  # GAVE/RECEIVED
        sa.Column('category', sa.String(50)),
        sa.Column('value', sa.Numeric(10,2)),  # RESTRICTED
        sa.Column('event_name', sa.String(200)),
        sa.Column('date', sa.Date),
        sa.Column('is_reciprocated', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

def downgrade():
    op.drop_table('favor_records')
    op.drop_table('contacts')
    op.execute('DROP TYPE IF EXISTS interaction_type_enum')
    op.execute('DROP TYPE IF EXISTS relation_type_enum')
    op.execute('DROP TYPE IF EXISTS contact_type_enum')
