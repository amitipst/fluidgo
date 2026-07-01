"""Initial schema — all fluidGo tables

Revision ID: 0001
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name',          sa.String(120), nullable=False),
        sa.Column('email',         sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('role',          sa.String(20), nullable=False),
        sa.Column('bu',            sa.String(50), server_default='West'),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table('dsr_daily',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('date',             sa.Date, nullable=False),
        sa.Column('status',           sa.String(20), server_default='working'),
        sa.Column('visits',           sa.Integer, server_default='0'),
        sa.Column('virtual_meetings', sa.Integer, server_default='0'),
        sa.Column('calls',            sa.Integer, server_default='0'),
        sa.Column('new_leads',        sa.Integer, server_default='0'),
        sa.Column('followups',        sa.Integer, server_default='0'),
        sa.Column('proposals',        sa.Integer, server_default='0'),
        sa.Column('notes',            sa.Text),
        sa.Column('submitted_at',     sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'date', name='uq_dsr_user_date'),
    )
    op.create_index('ix_dsr_user_date', 'dsr_daily', ['user_id', 'date'])
    op.create_table('self_scores',
        sa.Column('id',                   UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dsr_id',               UUID(as_uuid=True), sa.ForeignKey('dsr_daily.id', ondelete='CASCADE'), nullable=False),
        sa.Column('market_coverage',      sa.SmallInteger),
        sa.Column('lead_generation',      sa.SmallInteger),
        sa.Column('followup_discipline',  sa.SmallInteger),
        sa.Column('quality_of_conv',      sa.SmallInteger),
        sa.Column('commitment_to_close',  sa.SmallInteger),
    )
    op.create_table('meetings',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',           UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('date',              sa.Date, nullable=False),
        sa.Column('company',           sa.String(255), nullable=False),
        sa.Column('contact_name',      sa.String(120)),
        sa.Column('meeting_type',      sa.String(20)),
        sa.Column('discussion',        sa.Text),
        sa.Column('opportunity',       sa.Boolean, server_default='false'),
        sa.Column('support_needed',    sa.String(255)),
        sa.Column('bant_budget',       sa.Boolean),
        sa.Column('bant_authority',    sa.Boolean),
        sa.Column('bant_need',         sa.Boolean),
        sa.Column('bant_timeline',     sa.Boolean),
        sa.Column('ai_intent_score',   sa.String(20)),
        sa.Column('ai_closure_pct',    sa.SmallInteger),
        sa.Column('ai_recommendation', sa.Text),
        sa.Column('created_at',        sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table('leads',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('date',             sa.Date, nullable=False),
        sa.Column('company',          sa.String(255), nullable=False),
        sa.Column('contact_name',     sa.String(120)),
        sa.Column('requirement',      sa.Text),
        sa.Column('source',           sa.String(50)),
        sa.Column('next_action',      sa.Text),
        sa.Column('next_action_date', sa.Date),
        sa.Column('ai_lead_score',    sa.SmallInteger),
        sa.Column('status',           sa.String(30), server_default='new'),
        sa.Column('created_at',       sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table('pipeline',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',        UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('company',        sa.String(255), nullable=False),
        sa.Column('stage',          sa.String(20)),
        sa.Column('todays_update',  sa.Text),
        sa.Column('roadblock',      sa.Boolean, server_default='false'),
        sa.Column('next_step',      sa.Text),
        sa.Column('closure_eta',    sa.Date),
        sa.Column('deal_value',     sa.Numeric(12, 2)),
        sa.Column('ai_bant_score',  sa.SmallInteger),
        sa.Column('ai_closure_pct', sa.SmallInteger),
        sa.Column('created_at',     sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at',     sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table('ai_insights',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_type',  sa.String(30)),
        sa.Column('entity_id',    UUID(as_uuid=True)),
        sa.Column('insight_type', sa.String(30)),
        sa.Column('content',      sa.Text),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

def downgrade():
    for t in ['ai_insights','pipeline','leads','meetings','self_scores','dsr_daily','users']:
        op.drop_table(t)
