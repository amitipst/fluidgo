"""Add pre-sales DSR fields to dsr_daily.

Pre-sales activities logged in the same DSR row — role-conditional UI,
single DB table, single submission endpoint. No separate table needed.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

def upgrade():
    # Pre-Sales specific activity fields
    op.add_column('dsr_daily', sa.Column('demos_conducted',       sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('pocs_conducted',        sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('proposals_supported',   sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('tech_discussions',      sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('workshops_conducted',   sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('trainings_delivered',   sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('trainings_attended',    sa.Integer, server_default='0', nullable=False))
    op.add_column('dsr_daily', sa.Column('docs_created',          sa.Integer, server_default='0', nullable=False))
    # Linked opportunity (for pre-sales to tag which deal they supported)
    op.add_column('dsr_daily', sa.Column('linked_opportunity_id', sa.String(36), nullable=True))
    # DSR type — 'sales' | 'presales' (auto-set from user role on submit)
    op.add_column('dsr_daily', sa.Column('dsr_type', sa.String(20), server_default='sales', nullable=False))
    # Proposal value tracked (for sales reps)
    op.add_column('dsr_daily', sa.Column('proposal_value', sa.Numeric(14, 2), nullable=True))
    # Travel indicator
    op.add_column('dsr_daily', sa.Column('travel_day', sa.Boolean, server_default='false', nullable=False))

    # Add pre-sales specific self-score dimensions
    op.add_column('self_scores', sa.Column('solution_support',      sa.SmallInteger, nullable=True))
    op.add_column('self_scores', sa.Column('technical_conversion',  sa.SmallInteger, nullable=True))
    op.add_column('self_scores', sa.Column('knowledge_excellence',  sa.SmallInteger, nullable=True))
    op.add_column('self_scores', sa.Column('operational_excellence', sa.SmallInteger, nullable=True))

    # Index for fast date-range queries per dsr_type
    op.create_index('ix_dsr_type_date', 'dsr_daily', ['dsr_type', 'date'])

def downgrade():
    op.drop_index('ix_dsr_type_date', 'dsr_daily')
    for col in ['demos_conducted','pocs_conducted','proposals_supported','tech_discussions',
                'workshops_conducted','trainings_delivered','trainings_attended','docs_created',
                'linked_opportunity_id','dsr_type','proposal_value','travel_day']:
        op.drop_column('dsr_daily', col)
    for col in ['solution_support','technical_conversion','knowledge_excellence','operational_excellence']:
        op.drop_column('self_scores', col)
