"""CSG Phase 2 — Meeting Management + AI MOM Generator.

Extends the existing `meetings` table rather than creating a parallel one
(it already has the right shape: date/company/contact/discussion/status).
Meetings were Sales-only (BANT-focused) and disconnected from both
DSRDaily.virtual_meetings and DORDaily.client_meetings_held — two manually
-typed counters with no rows behind them. This migration generalizes the
table to also serve Service Delivery (QBR/cadence/escalation reviews) and
links it back to the daily log it came from, closing both disconnects
symmetrically.

All columns nullable-with-default — additive, zero risk to existing rows,
same philosophy as PipelineDeal's v2 fields (migration 0018) and the CSG
Phase 1 account_id soft-refs already on PipelineDeal/DORDaily.

  - source          'sales' | 'service_delivery' — who logged it, mirrors
                     PipelineDeal.source exactly.
  - account_id       soft ref -> accounts.id (see Account, migration 0018).
                     Resolved via account_service.get_or_create_account()
                     the same way DOR's flag-opportunity already does.
  - dsr_id           soft ref -> dsr_daily.id. Set when source='sales' and
                     a DSR row exists for that user+date.
  - dor_id           soft ref -> dor_daily.id. Set when source=
                     'service_delivery' and a DOR row exists for that
                     user+date.
  - meeting_purpose  free string, not a DB enum on purpose — QBR/cadence/
                     escalation-review/etc are a growing, config-like list;
                     a new purpose should never need a migration.
  - attendees        JSONB list of {name, title, is_external} — optional,
                     manual entry for Phase 2 (AI attendee-extraction is a
                     later refinement, not required for MOM generation).
  - ai_mom_summary / ai_mom_generated_at / mom_status — AI-generated
                     Minutes of Meeting (markdown, same pattern as every
                     other AI output in this codebase — deal_health,
                     deal_momentum, daily_insight are all markdown blobs,
                     not structured JSON; phi3:mini is too small to trust
                     for reliable JSON extraction). mom_status
                     (none|generated|edited|finalized) gives a human a
                     required checkpoint before the AI draft is treated as
                     authoritative.

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('meetings', sa.Column(
        'source', sa.String(20), server_default='sales', nullable=False))
    op.add_column('meetings', sa.Column(
        'account_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('meetings', sa.Column(
        'dsr_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('meetings', sa.Column(
        'dor_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('meetings', sa.Column(
        'meeting_purpose', sa.String(30), server_default='sales_discovery', nullable=True))
    op.add_column('meetings', sa.Column(
        'attendees', postgresql.JSONB(), nullable=True))
    op.add_column('meetings', sa.Column(
        'ai_mom_summary', sa.Text(), nullable=True))
    op.add_column('meetings', sa.Column(
        'ai_mom_generated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meetings', sa.Column(
        'mom_status', sa.String(20), server_default='none', nullable=False))


def downgrade():
    op.drop_column('meetings', 'mom_status')
    op.drop_column('meetings', 'ai_mom_generated_at')
    op.drop_column('meetings', 'ai_mom_summary')
    op.drop_column('meetings', 'attendees')
    op.drop_column('meetings', 'meeting_purpose')
    op.drop_column('meetings', 'dor_id')
    op.drop_column('meetings', 'dsr_id')
    op.drop_column('meetings', 'account_id')
    op.drop_column('meetings', 'source')
