"""Extend the seed-data flag (migration 0027) to pipeline deals and leads.

Root cause: 0027 added `is_seed` to dsr_daily and meetings only, because that
pass was scoped to the specific symptom reported at the time (dummy Meetings
list + polluted Analytics charts). A follow-up audit (2026-07-22, triggered
by a screenshot of Team Win-Loss Analysis showing 35 WON / 15 LOST / 0 ON
HOLD / 23 DROPPED with "Top loss reasons: unspecified (15)") found the exact
same seed_v3.py placeholder-data problem on `pipeline` (PipelineDeal) and
`leads` (Lead) — neither table had ANY way to exclude seed rows. `pipeline`
does have `archived` (migration 0026), but that flag was never set on seeded
rows either (it's an admin action on a real deal, not a seed marker), and
several read paths (loss_analysis, scoring_engine's metric registry, revenue
analytics, funnel analytics) didn't even apply `archived` where it already
existed. This migration only adds the missing flag+backfill; the query-level
fixes are separate application-code changes in this same pass.

Backfill cutoff: same 2026-07-04 go-live date used in 0027. PipelineDeal has
no single "which day did this happen" column as clean as DSRDaily/Meeting's
`date` (closure_eta is deliberately spread into the future by seed_v3.py, so
it can't be used as a seed marker) — `created_at` is used instead, since
seed_v3.py inserts all its placeholder rows in one seeding run and that
timestamp reliably clusters at seed time. Same reasoning for Lead.

This is a blunt, timestamp-based instrument like 0027 — a genuine deal/lead
created before 2026-07-04 would also get flagged; recoverable via
include_seed=true (where offered) + manual unset if any are found.

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None

SEED_CUTOFF = "2026-07-04"


def upgrade():
    op.add_column('pipeline', sa.Column(
        'is_seed', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('leads', sa.Column(
        'is_seed', sa.Boolean(), server_default='false', nullable=False))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE pipeline SET is_seed = true WHERE created_at < :cutoff"
    ), {"cutoff": SEED_CUTOFF})
    conn.execute(sa.text(
        "UPDATE leads SET is_seed = true WHERE created_at < :cutoff"
    ), {"cutoff": SEED_CUTOFF})


def downgrade():
    op.drop_column('leads', 'is_seed')
    op.drop_column('pipeline', 'is_seed')
