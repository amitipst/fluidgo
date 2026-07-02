"""v2 foundation — Opportunity fields on pipeline, org-role hierarchy, config-driven
scoring engine tables, revenue targets. Fully additive: no existing column dropped,
renamed, or made non-nullable.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    # org_roles first — everything else FKs into it
    op.create_table('org_roles',
        sa.Column('role_key',        sa.String(30), primary_key=True),
        sa.Column('display_name',    sa.String(100), nullable=False),
        sa.Column('parent_role_key', sa.String(30), sa.ForeignKey('org_roles.role_key')),
        sa.Column('data_scope',      sa.String(20), nullable=False),
    )

    op.add_column('users', sa.Column('org_role_key', sa.String(30),
                                      sa.ForeignKey('org_roles.role_key'), nullable=True))

    # ── Opportunity fields on the existing pipeline table ──
    op.add_column('pipeline', sa.Column('bu',                sa.String(50)))
    op.add_column('pipeline', sa.Column('presales_owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id')))
    op.add_column('pipeline', sa.Column('primary_contact',   sa.String(120)))
    op.add_column('pipeline', sa.Column('oem',                sa.String(100)))
    op.add_column('pipeline', sa.Column('solution_area',     sa.String(100)))
    op.add_column('pipeline', sa.Column('practice',          sa.String(100)))
    op.add_column('pipeline', sa.Column('recurring_revenue', sa.Numeric(12, 2)))
    op.add_column('pipeline', sa.Column('one_time_revenue',  sa.Numeric(12, 2)))
    op.add_column('pipeline', sa.Column('gross_margin_pct',  sa.Numeric(5, 2)))
    op.add_column('pipeline', sa.Column('competition',       sa.Text))
    op.add_column('pipeline', sa.Column('risk_level',        sa.String(20)))
    op.add_column('pipeline', sa.Column('decision_maker',    sa.String(120)))
    op.add_column('pipeline', sa.Column('budget_status',     sa.String(30)))
    op.add_column('pipeline', sa.Column('timeline_status',   sa.String(30)))
    op.add_column('pipeline', sa.Column('proposal_version',  sa.String(20)))
    op.add_column('pipeline', sa.Column('last_activity_at',  sa.DateTime(timezone=True)))
    op.add_column('pipeline', sa.Column('next_followup_at',  sa.DateTime(timezone=True)))
    op.add_column('pipeline', sa.Column('ai_deal_health',       sa.SmallInteger))
    op.add_column('pipeline', sa.Column('ai_deal_health_label', sa.String(30)))

    # ── Config-driven scoring engine ──
    op.create_table('scoring_templates',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name',       sa.String(100), nullable=False),
        sa.Column('role_key',   sa.String(30), sa.ForeignKey('org_roles.role_key'), nullable=False),
        sa.Column('version',    sa.Integer, server_default='1'),
        sa.Column('is_active',  sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table('scoring_parameters',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('template_id',   UUID(as_uuid=True), sa.ForeignKey('scoring_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name',          sa.String(100), nullable=False),
        sa.Column('weight_pct',    sa.Numeric(5, 2), nullable=False),
        sa.Column('metric_source', sa.String(100), nullable=False),
        sa.Column('calc_type',     sa.String(20), server_default='pct'),
        sa.Column('sort_order',    sa.Integer, server_default='0'),
    )
    op.create_table('scoring_results',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',     UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('template_id', UUID(as_uuid=True), sa.ForeignKey('scoring_templates.id'), nullable=False),
        sa.Column('period',      sa.String(20), nullable=False),
        sa.Column('score',       sa.Numeric(5, 2), nullable=False),
        sa.Column('breakdown',   JSONB),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_scoring_results_user_period', 'scoring_results', ['user_id', 'period'])

    op.create_table('revenue_targets',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',       UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('period',        sa.String(20), nullable=False),
        sa.Column('target_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'period', name='uq_revenue_target_user_period'),
    )

def downgrade():
    op.drop_table('revenue_targets')
    op.drop_index('ix_scoring_results_user_period', table_name='scoring_results')
    op.drop_table('scoring_results')
    op.drop_table('scoring_parameters')
    op.drop_table('scoring_templates')
    for col in ['ai_deal_health_label', 'ai_deal_health', 'next_followup_at', 'last_activity_at',
                'proposal_version', 'timeline_status', 'budget_status', 'decision_maker',
                'risk_level', 'competition', 'gross_margin_pct', 'one_time_revenue',
                'recurring_revenue', 'practice', 'solution_area', 'oem', 'primary_contact',
                'presales_owner_id', 'bu']:
        op.drop_column('pipeline', col)
    op.drop_column('users', 'org_role_key')
    op.drop_table('org_roles')
