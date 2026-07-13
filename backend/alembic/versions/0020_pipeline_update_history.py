"""Pipeline update history: "Today's Update" / "Next Step" were overwritten
in place on every Save, losing the trail of what a rep reported over time.
This adds an append-only history table so every remark is retained, visible
as a timeline on the deal, and usable as an ordered sequence for AI trend
analysis (stall detection, momentum summaries via the existing Ollama
post-mortem pattern in pipeline.py). Purely additive - zero risk to
existing pipeline rows. deal_id/author_id are soft references (no FK
constraint), consistent with account_id/presales_owner_id elsewhere in
this schema.

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pipeline_updates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('update_text', sa.Text(), nullable=False),
        sa.Column('next_step', sa.Text(), nullable=True),
        sa.Column('stage_at_time', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_pipeline_updates_deal_id', 'pipeline_updates', ['deal_id'])


def downgrade():
    op.drop_index('ix_pipeline_updates_deal_id', table_name='pipeline_updates')
    op.drop_table('pipeline_updates')
