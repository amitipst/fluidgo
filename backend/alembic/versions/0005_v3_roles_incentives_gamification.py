"""v3 Role system — expand roles, add multi-BU, incentive/gamification tables

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade():
    # ── Expand users.role to include new roles ────────────────────────────
    # Drop old check constraint (if any) and widen the column
    # New roles: rep | inside_sales | pre_sales | manager | bu_head |
    #            business_head | hr | finance | ceo | super_admin
    op.alter_column('users', 'role',
                    type_=sa.String(30), existing_type=sa.String(20))

    # ── Add business field to users ───────────────────────────────────────
    # Which product-line business the user belongs to
    # fluidpro | fluidprint | floxtax | hooks
    op.add_column('users', sa.Column('business', sa.String(50),
                                     nullable=True, server_default='fluidpro'))

    # ── Add manager_id (direct reporting line) ────────────────────────────
    op.add_column('users', sa.Column('manager_id', UUID(as_uuid=True),
                                     sa.ForeignKey('users.id', ondelete='SET NULL'),
                                     nullable=True))

    # ── Incentive Schemes table ───────────────────────────────────────────
    # Created by Manager or BU Head for a specific period
    op.create_table('incentive_schemes',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_by',   UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('bu',           sa.String(50), nullable=False),
        sa.Column('business',     sa.String(50), nullable=False, server_default='fluidpro'),
        # Scope: 'team' = only manager's direct reports, 'bu' = whole BU
        sa.Column('scope',        sa.String(20), nullable=False, server_default='bu'),
        sa.Column('name',         sa.String(100), nullable=False),
        sa.Column('description',  sa.Text, nullable=True),
        sa.Column('period',       sa.String(20), nullable=False),   # "2026-07"
        sa.Column('status',       sa.String(20), server_default='active'),  # active|paused|closed
        # What metric to measure
        sa.Column('metric',       sa.String(50), nullable=False),
        # e.g. "calls", "visits", "new_leads", "proposals", "closed_won_value",
        #      "rigor_avg", "followups", "bant_meetings"
        sa.Column('target_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('reward_type',  sa.String(30), nullable=False),   # cash|points|badge|recognition
        sa.Column('reward_value', sa.Numeric(10, 2), nullable=True),  # cash amount or points
        sa.Column('reward_badge', sa.String(50), nullable=True),    # e.g. "hat_trick", "deal_king"
        sa.Column('created_at',   sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at',   sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_incentive_bu_period', 'incentive_schemes', ['bu', 'period'])

    # ── Gamification points ledger ────────────────────────────────────────
    op.create_table('points_ledger',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',     UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('scheme_id',   UUID(as_uuid=True), sa.ForeignKey('incentive_schemes.id',
                                                                    ondelete='CASCADE'), nullable=True),
        sa.Column('period',      sa.String(20), nullable=False),
        sa.Column('points',      sa.Integer, nullable=False, server_default='0'),
        sa.Column('reason',      sa.String(200), nullable=True),
        sa.Column('source',      sa.String(50), nullable=True),  # scheme|manual|badge|streak
        sa.Column('awarded_at',  sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_points_user_period', 'points_ledger', ['user_id', 'period'])

    # ── Badges earned ─────────────────────────────────────────────────────
    op.create_table('user_badges',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',     UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('badge_key',   sa.String(50), nullable=False),
        sa.Column('badge_name',  sa.String(100), nullable=False),
        sa.Column('period',      sa.String(20), nullable=True),
        sa.Column('awarded_at',  sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'badge_key', 'period', name='uq_user_badge_period'),
    )

    # ── Revenue targets: add business field ───────────────────────────────
    op.add_column('revenue_targets', sa.Column('business', sa.String(50),
                                                nullable=True, server_default='fluidpro'))

    # ── Scoring results: add business field ──────────────────────────────
    op.add_column('scoring_results', sa.Column('business', sa.String(50),
                                                nullable=True, server_default='fluidpro'))

def downgrade():
    op.drop_table('user_badges')
    op.drop_table('points_ledger')
    op.drop_index('ix_incentive_bu_period', 'incentive_schemes')
    op.drop_table('incentive_schemes')
    op.drop_column('users', 'manager_id')
    op.drop_column('users', 'business')
    op.drop_column('scoring_results', 'business')
    op.drop_column('revenue_targets', 'business')
