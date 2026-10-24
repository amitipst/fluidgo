"""company_kpi_entries — org-wide (not per-user) manual KPI values

FGA parameter design (Amit, 2026-10-24): up to 5 scoring parameters per role
template, 3 "self-performance" (individual, already supported by the existing
METRIC_REGISTRY / manual.* ManualMetricEntry machinery) + up to 1
"company-performance" parameter (e.g. Company Revenue Target, weight 30% when
enabled). A company-wide number entered once per period must NOT reuse
ManualMetricEntry — that table is keyed by (user_id, metric_key, period), so
an org-wide figure would need Finance to re-enter the identical number once
per rep, which is both tedious and a real risk of two reps' entries silently
disagreeing (exactly the kind of inconsistency Amit flagged wanting FGA
validation to catch). This table is keyed by (metric_key, period) only — one
row serves every role/user whose template references it.

Shipped DISABLED: no ScoringParameter row references 'company_manual.*' yet
in any live template (see scoring_engine.py's COMPANY_MANUAL_METRICS comment)
— this migration adds capacity only, zero effect on any score until a human
explicitly adds the parameter via Scoring Admin and sets its weight.

Revision ID: 0037
Revises: 0036
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'company_kpi_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('metric_key', sa.String(100), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('value', sa.Numeric(8, 3), nullable=False),
        sa.Column('raw_inputs', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('entered_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    # One row per (metric_key, period) — upserted on re-entry, mirrors
    # manual_metric_entries' per-user uniqueness but org-wide instead.
    op.create_unique_constraint(
        'uq_company_kpi_entries_metric_period', 'company_kpi_entries',
        ['metric_key', 'period'],
    )


def downgrade():
    op.drop_constraint('uq_company_kpi_entries_metric_period', 'company_kpi_entries', type_='unique')
    op.drop_table('company_kpi_entries')
