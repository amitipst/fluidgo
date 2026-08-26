"""Governance role support — audit-trail columns for the new "governance"
role (see ROLE_HIERARCHY in app/models/__init__.py).

Governance validates DSR/DMR/DOR and FGA submissions for completeness and
timeliness — it has NO data-entry obligation of its own and NO approval
authority (that stays with the existing manager/HR/VP chain), and per
Amit's explicit ask, no visibility into revenue/incentive/score figures
(enforced in application code via can_see_financials() / deny_governance(),
not by this migration). What governance DOES need is a way to record "I
reviewed this and it's fine" or "I reviewed this and I'm flagging it" —
without touching the real approval_status/score fields those roles own.

This adds four columns, mirroring the existing approved_by/approved_at/
manager_comment pattern already on these tables, to dsr_daily, dor_daily,
and scoring_results (the three things governance validates — DSR/DMR share
dsr_daily, DOR is dor_daily, FGA is scoring_results):
  - governance_reviewed_by  (who)
  - governance_reviewed_at  (when)
  - governance_flag         (did they flag it — bool, default false)
  - governance_comment      (why, if flagged)

Deliberately independent of approval_status — a governance review is a
parallel compliance checkpoint, not an extra stage in the approval chain,
so it can never become a bottleneck on the real approve/reject/payout flow.

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None

_TABLES = ('dsr_daily', 'dor_daily', 'scoring_results')


def upgrade():
    for table in _TABLES:
        op.add_column(table, sa.Column(
            'governance_reviewed_by', postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column(
            'governance_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column(
            'governance_flag', sa.Boolean(), server_default='false', nullable=False))
        op.add_column(table, sa.Column(
            'governance_comment', sa.Text(), nullable=True))


def downgrade():
    for table in _TABLES:
        op.drop_column(table, 'governance_comment')
        op.drop_column(table, 'governance_flag')
        op.drop_column(table, 'governance_reviewed_at')
        op.drop_column(table, 'governance_reviewed_by')
