"""Create finance tables

Revision ID: 005_create_finance_tables
Revises: 004_create_growth_tables
Create Date: 2025-11-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '005_create_finance_tables'
down_revision = '004_create_growth_tables'

def upgrade() -> None:
    # Transaction types enum
    op.execute("""
        CREATE TYPE transaction_type_enum AS ENUM ('INCOME', 'EXPENSE');
        CREATE TYPE transaction_source_enum AS ENUM ('CONVERSATION', 'OCR', 'MANUAL', 'IMPORT');
        CREATE TYPE period_type_enum AS ENUM ('MONTHLY', 'QUARTERLY', 'YEARLY');
        CREATE TYPE budget_type_enum AS ENUM ('CATEGORY', 'TOTAL', 'CUSTOM');
    """)
    
    # financial_transactions table (partitioned by month)
    op.execute("""
        CREATE TABLE financial_transactions (
            transaction_id UUID PRIMARY KEY,
            family_id UUID NOT NULL,
            transaction_type transaction_type_enum NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            category VARCHAR(50) NOT NULL,
            description TEXT,
            transaction_date DATE NOT NULL,
            source transaction_source_enum DEFAULT 'MANUAL',
            member_id UUID,
            ocr_confidence FLOAT,
            encrypted_amount BYTEA,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        ) PARTITION BY RANGE (transaction_date);
        
        CREATE INDEX idx_transactions_family ON financial_transactions(family_id);
        CREATE INDEX idx_transactions_date ON financial_transactions(transaction_date);
        CREATE INDEX idx_transactions_category ON financial_transactions(category);
    """)
    
    # Create initial partitions for 2025
    for month in range(1, 13):
        start_date = f"2025-{month:02d}-01"
        if month == 12:
            end_date = "2026-01-01"
        else:
            end_date = f"2025-{month+1:02d}-01"
        
        op.execute(f"""
            CREATE TABLE financial_transactions_2025_{month:02d} 
            PARTITION OF financial_transactions
            FOR VALUES FROM ('{start_date}') TO ('{end_date}');
        """)
    
    # budgets table
    op.create_table(
        'budgets',
        sa.Column('budget_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('budget_type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50)),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('period_start', sa.Date, nullable=False),
        sa.Column('period_end', sa.Date, nullable=False),
        sa.Column('amount_limit', sa.Numeric(12, 2), nullable=False),
        sa.Column('current_usage', sa.Numeric(12, 2), default=0),
        sa.Column('usage_rate', sa.Float, default=0),
        sa.Column('exceeded', sa.Boolean, default=False),
        sa.Column('alert_threshold', sa.Float, default=0.9),
        sa.Column('alert_sent', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime),
    )
    
    # monthly_reports table
    op.create_table(
        'monthly_reports',
        sa.Column('report_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('report_month', sa.Date, nullable=False),
        sa.Column('total_income', sa.Numeric(12, 2), default=0),
        sa.Column('total_expense', sa.Numeric(12, 2), default=0),
        sa.Column('balance', sa.Numeric(12, 2), default=0),
        sa.Column('savings_rate', sa.Float, default=0),
        sa.Column('category_breakdown', JSONB),
        sa.Column('anomalies_detected', JSONB),
        sa.Column('ai_analysis', sa.Text),
        sa.Column('generated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

def downgrade() -> None:
    op.drop_table('monthly_reports')
    op.drop_table('budgets')
    op.execute('DROP TABLE financial_transactions CASCADE')
    op.execute('DROP TYPE IF EXISTS budget_type_enum')
    op.execute('DROP TYPE IF EXISTS period_type_enum')
    op.execute('DROP TYPE IF EXISTS transaction_source_enum')
    op.execute('DROP TYPE IF EXISTS transaction_type_enum')
