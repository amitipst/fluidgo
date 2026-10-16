"""Pipeline forecast sheet (v1.5.0): rep win probability, target note, target-change ledger.

Additive and nullable only — safe on a live DB, no backfill.
Revision ID: 0036
Revises: 0035
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pipeline', sa.Column('win_probability', sa.SmallInteger(), nullable=True))
    op.add_column('pipeline', sa.Column('target_note', sa.String(60), nullable=True))
    op.create_table(
        'pipeline_target_changes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_label', sa.String(60), nullable=True),
        sa.Column('new_label', sa.String(60), nullable=True),
        sa.Column('reason', sa.String(300), nullable=True),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_pipeline_target_changes_deal', 'pipeline_target_changes', ['deal_id', 'changed_at'])


def downgrade():
    op.drop_index('ix_pipeline_target_changes_deal', table_name='pipeline_target_changes')
    op.drop_table('pipeline_target_changes')
    op.drop_column('pipeline', 'target_note')
    op.drop_column('pipeline', 'win_probability')
