"""Add FGA approval workflow columns to scoring_results

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('scoring_results', sa.Column('approval_status', sa.String(30), nullable=True, server_default='pending_manager'))
    op.add_column('scoring_results', sa.Column('override_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('scoring_results', sa.Column('manager_comment', sa.Text, nullable=True))
    op.add_column('scoring_results', sa.Column('hr_comment', sa.Text, nullable=True))
    op.add_column('scoring_results', sa.Column('vp_comment', sa.Text, nullable=True))
    op.add_column('scoring_results', sa.Column('reviewed_by_manager_id', UUID(as_uuid=True), nullable=True))
    op.add_column('scoring_results', sa.Column('reviewed_by_hr_id', UUID(as_uuid=True), nullable=True))
    op.add_column('scoring_results', sa.Column('reviewed_by_vp_id', UUID(as_uuid=True), nullable=True))
    op.add_column('scoring_results', sa.Column('manager_reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('scoring_results', sa.Column('hr_reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('scoring_results', sa.Column('vp_reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_scoring_results_period_status', 'scoring_results', ['period', 'approval_status'])

def downgrade():
    op.drop_index('ix_scoring_results_period_status', 'scoring_results')
    for col in ['approval_status','override_score','manager_comment','hr_comment','vp_comment',
                'reviewed_by_manager_id','reviewed_by_hr_id','reviewed_by_vp_id',
                'manager_reviewed_at','hr_reviewed_at','vp_reviewed_at']:
        op.drop_column('scoring_results', col)
