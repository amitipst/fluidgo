"""Win-loss analysis + contract win-back fields on pipeline.

All columns nullable/additive — zero risk to existing rows.

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('pipeline', sa.Column('outcome_category',    sa.String(50), nullable=True))
    op.add_column('pipeline', sa.Column('outcome_detail',      sa.Text, nullable=True))
    op.add_column('pipeline', sa.Column('outcome_competitor',  sa.String(120), nullable=True))
    op.add_column('pipeline', sa.Column('outcome_recorded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pipeline', sa.Column('outcome_ai_analysis', sa.Text, nullable=True))
    op.add_column('pipeline', sa.Column('contract_months',     sa.Integer, nullable=True))
    op.add_column('pipeline', sa.Column('contract_end_date',   sa.Date, nullable=True))
    op.add_column('pipeline', sa.Column('reengage_at',         sa.Date, nullable=True))
    op.add_column('pipeline', sa.Column('reengage_done',       sa.Boolean, server_default='false', nullable=False))

def downgrade():
    for col in ['reengage_done', 'reengage_at', 'contract_end_date', 'contract_months',
                'outcome_ai_analysis', 'outcome_recorded_at', 'outcome_competitor',
                'outcome_detail', 'outcome_category']:
        op.drop_column('pipeline', col)
