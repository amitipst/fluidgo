"""Service Delivery Manager FGA + DOR: tiered/manual scoring parameters,
manual metric entries, and the DOR daily-ops table.

All additive — zero risk to existing rows.

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    # ── scoring_parameters: tiered/manual + enable-disable support ─────────
    op.add_column('scoring_parameters', sa.Column('tiers', postgresql.JSONB, nullable=True))
    op.add_column('scoring_parameters', sa.Column(
        'is_active', sa.Boolean, server_default='true', nullable=False))

    # ── manual_metric_entries ───────────────────────────────────────────────
    op.create_table(
        'manual_metric_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_key', sa.String(100), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('value', sa.Numeric(8, 3), nullable=False),
        sa.Column('raw_inputs', postgresql.JSONB, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('entered_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        'uq_manual_metric_user_key_period', 'manual_metric_entries',
        ['user_id', 'metric_key', 'period'],
    )

    # ── dor_daily ────────────────────────────────────────────────────────────
    op.create_table(
        'dor_daily',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_date', sa.Date, nullable=False),
        sa.Column('client_account', sa.String(150), nullable=True),
        sa.Column('status', sa.String(20), server_default='on_track', nullable=False),
        sa.Column('tickets_open_start', sa.Integer, server_default='0', nullable=False),
        sa.Column('tickets_new', sa.Integer, server_default='0', nullable=False),
        sa.Column('tickets_closed', sa.Integer, server_default='0', nullable=False),
        sa.Column('tickets_overdue', sa.Integer, server_default='0', nullable=False),
        sa.Column('escalations_raised', sa.Integer, server_default='0', nullable=False),
        sa.Column('escalations_resolved', sa.Integer, server_default='0', nullable=False),
        sa.Column('collection_calls_made', sa.Integer, server_default='0', nullable=False),
        sa.Column('collection_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('client_meetings_held', sa.Integer, server_default='0', nullable=False),
        sa.Column('resource_deployed', sa.Integer, nullable=True),
        sa.Column('resource_available', sa.Integer, nullable=True),
        sa.Column('blockers_notes', sa.Text, nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        'uq_dor_daily_user_date', 'dor_daily', ['user_id', 'report_date'],
    )


def downgrade():
    op.drop_table('dor_daily')
    op.drop_table('manual_metric_entries')
    op.drop_column('scoring_parameters', 'is_active')
    op.drop_column('scoring_parameters', 'tiers')
