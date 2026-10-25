"""lead_spanco_stage_and_feature_flags — Leads SPANCO stage ladder + a
generic feature_flags config/toggle table

Built overnight 2026-10-24 -> 25 under a Rambo Commander handoff
("now i am going to sleep, rambo to mkeep continue" / "morning will sync
with git and deploy on ec2"), in direct response to two instructions Amit
gave in the same session:

1. Five screenshots of WEP Solutions' own live Kylas CRM (app.kylas.io/
   sales/leads/list) handing over what he called "the right SPANCO" — an
   11-column Leads stage ladder (SP1 Identifying Opportunities .. SP7
   Negotiation, then Hold / Won / Closed Unqualified / Closed Lost) — plus
   "kanban view is good to have (challenge and see what best can come to
   our platform)".
2. "ensure the product scalability and a MSP where standard features can
   be offered and wepsol customized can be disabled/enabled as per
   customer requirement" — answered here by making the stage ladder and
   the Kanban view both config-driven via `feature_flags`, never hardcoded
   in a frontend constant the way the pre-existing Pipeline.tsx STAGES list
   is (that list's own code comment already flags the drift risk this
   migration avoids for Leads).

This does NOT implement multi-tenancy (fluidgo-roadmap-v2.md decision gate
#1). `feature_flags.org_scope` is nullable and unused today — no
org/account/tenant entity exists anywhere in this schema, and none is added
here. It is present only so a future per-customer override needs an INSERT
against an existing table, not a schema migration.

NAMING CONFLICT — flagged for Amit, not resolved silently: this SPANCO
ladder lives on `leads` and is sourced from Kylas's Leads screen. A
*different* 6-stage S(uspecting)-P(rospecting)-A(nalysing)-N(egotiating)-
C(losing)-O(rder) draft already exists in
fluidgo-mom-action-governance-design.md §11, scoped to `pipeline`
(PipelineDeal/Opportunity), dated 2026-10-13, and was itself still "awaiting
confirmation." Both are real, both are called SPANCO, and they are
different stage counts on different entities. See claude/README.md Open
Items — do not assume this migration settles which one wins.

Two of Kylas's seven labels were truncated in the screenshots
("Scope Finalization/P..." and "Techno-Commercial ...") — SP5 and SP6 below
are a best-effort reconstruction, not a transcription. Confirm the exact
wording against the live Kylas instance before treating them as final.

Revision ID: 0038
Revises: 0037
"""
import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None

# Kept in sync by hand with app.services.lead_stage_service.DEFAULT_LEAD_STAGES
# — this migration seeds a real feature_flags row with the same content so
# "edit the ladder for this customer" is an UPDATE on day one, not a first
# INSERT someone has to remember to add before the override does anything.
_STAGES = [
    {"key": "sp1_identifying",        "label": "SP1 · Identifying Opportunities",    "sort_order": 1,  "is_terminal": False, "outcome": None,   "color": "#94A3B8"},
    {"key": "sp2_profiling_bant",     "label": "SP2 · Profiling (BANT)",              "sort_order": 2,  "is_terminal": False, "outcome": None,   "color": "#60A5FA"},
    {"key": "sp3_understanding",      "label": "SP3 · Understanding the Opportunity", "sort_order": 3,  "is_terminal": False, "outcome": None,   "color": "#38BDF8"},
    {"key": "sp4_qualification_bant", "label": "SP4 · Qualification (BANT)",          "sort_order": 4,  "is_terminal": False, "outcome": None,   "color": "#34D399"},
    {"key": "sp5_scope_proposal",     "label": "SP5 · Scope Finalization / Proposal", "sort_order": 5,  "is_terminal": False, "outcome": None,   "color": "#A78BFA"},
    {"key": "sp6_techno_commercial",  "label": "SP6 · Techno-Commercial Discussion",  "sort_order": 6,  "is_terminal": False, "outcome": None,   "color": "#F472B6"},
    {"key": "sp7_negotiation",        "label": "SP7 · Negotiation",                   "sort_order": 7,  "is_terminal": False, "outcome": None,   "color": "#FB923C"},
    {"key": "hold",                   "label": "Hold",                                     "sort_order": 8,  "is_terminal": False, "outcome": None,   "color": "#CBD5E1"},
    {"key": "won",                    "label": "Won",                                      "sort_order": 9,  "is_terminal": True,  "outcome": "won",  "color": "#22C55E"},
    {"key": "closed_unqualified",     "label": "Closed · Unqualified",                "sort_order": 10, "is_terminal": True,  "outcome": "lost", "color": "#9CA3AF"},
    {"key": "closed_lost",            "label": "Closed · Lost",                       "sort_order": 11, "is_terminal": True,  "outcome": "lost", "color": "#EF4444"},
]


def upgrade():
    op.add_column('leads', sa.Column('stage', sa.String(40), nullable=True))

    op.create_table(
        'feature_flags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('org_scope', sa.String(100), nullable=True),
        sa.Column('config', postgresql.JSONB(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_feature_flags_key', 'feature_flags', ['key'])

    # Backfill: give every existing lead a starting stage derived from its
    # current coarse status, so the Kanban board has somewhere real to put
    # them from day one instead of everything landing in column one.
    # Heuristic, not fact — see lead_stage_service.default_stage_for_status
    # docstring for the reasoning per status value (notably: 'converted'
    # lands on 'won', since the lead already did its job by becoming a
    # pipeline deal). Review/move individual leads at any time — stage is
    # nullable and this is purely additive.
    op.execute("""
        UPDATE leads SET stage = CASE status
            WHEN 'new' THEN 'sp1_identifying'
            WHEN 'qualified' THEN 'sp3_understanding'
            WHEN 'proposal' THEN 'sp5_scope_proposal'
            WHEN 'closed_won' THEN 'won'
            WHEN 'closed_lost' THEN 'closed_lost'
            WHEN 'converted' THEN 'won'
            ELSE 'sp1_identifying'
        END
        WHERE stage IS NULL
    """)

    conn = op.get_bind()
    conn.execute(
        sa.text("""
            INSERT INTO feature_flags (id, key, enabled, org_scope, config, updated_at)
            VALUES (:id, 'leads_spanco_stages', true, NULL, CAST(:cfg AS JSONB), now())
        """),
        {"id": str(uuid.uuid4()), "cfg": json.dumps({"stages": _STAGES})},
    )
    conn.execute(
        sa.text("""
            INSERT INTO feature_flags (id, key, enabled, org_scope, config, updated_at)
            VALUES (:id, 'leads_kanban_view', true, NULL, NULL, now())
        """),
        {"id": str(uuid.uuid4())},
    )


def downgrade():
    op.drop_index('ix_feature_flags_key', table_name='feature_flags')
    op.drop_table('feature_flags')
    op.drop_column('leads', 'stage')
