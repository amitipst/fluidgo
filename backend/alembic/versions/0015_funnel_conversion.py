"""Funnel conversion linkage: meeting → lead → deal (opportunity).

All columns nullable/additive — zero risk to existing rows.

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

def upgrade():
    # meetings: status + link to the lead it became
    op.add_column('meetings', sa.Column('status', sa.String(20),
                   server_default='logged', nullable=False))
    op.add_column('meetings', sa.Column('converted_to_lead_id', UUID(as_uuid=True), nullable=True))

    # leads: provenance (source meeting) + link to the deal it became
    op.add_column('leads', sa.Column('source_meeting_id', UUID(as_uuid=True), nullable=True))
    op.add_column('leads', sa.Column('converted_to_deal_id', UUID(as_uuid=True), nullable=True))

    # pipeline: provenance (source lead)
    op.add_column('pipeline', sa.Column('source_lead_id', UUID(as_uuid=True), nullable=True))

def downgrade():
    op.drop_column('pipeline', 'source_lead_id')
    op.drop_column('leads', 'converted_to_deal_id')
    op.drop_column('leads', 'source_meeting_id')
    op.drop_column('meetings', 'converted_to_lead_id')
    op.drop_column('meetings', 'status')
