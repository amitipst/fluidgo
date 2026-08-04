"""Seed-data flag for meetings & dsr_daily. Root cause of "dummy data
pollutes Analytics and Meetings" (see fluidGo data-quality review,
2026-07-21): seed_v3.py attaches placeholder rows (e.g. contact_name=
"Mr/Ms Contact N") to REAL production accounts (danish@fluidpro.in,
neha@fluidpro.in among others), and there was no flag anywhere to tell a
seeded row apart from a real one. This mirrors the 0026 pipeline-archive
pattern: add a boolean marker, default-exclude it from list/analytics
queries, keep an admin-only include_seed opt-in for verification — data
is never deleted, just hidden by default.

Backfill: seed_v3.py seeded DSR/meetings from 2026-04-01 through
2026-07-02; real usage began ~2026-07-04 (this is the exact date the
"Daily Calls & Follow-ups" chart shows a hard discontinuity). Anything
dated before 2026-07-04 is flagged is_seed=true here. This is a blunt
instrument by date rather than by origin (there's no created-by-script
marker on existing rows to key off instead) — if a real rep logged a
genuine DSR/meeting before 2026-07-04 it will also get flagged and drop
out of default views; re-run with include_seed=true to check for any
such rows and unset is_seed on them individually if found.

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None

SEED_CUTOFF = "2026-07-04"


def upgrade():
    op.add_column('dsr_daily', sa.Column(
        'is_seed', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('meetings', sa.Column(
        'is_seed', sa.Boolean(), server_default='false', nullable=False))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE dsr_daily SET is_seed = true WHERE date < :cutoff"
    ), {"cutoff": SEED_CUTOFF})
    conn.execute(sa.text(
        "UPDATE meetings SET is_seed = true WHERE date < :cutoff"
    ), {"cutoff": SEED_CUTOFF})


def downgrade():
    op.drop_column('meetings', 'is_seed')
    op.drop_column('dsr_daily', 'is_seed')
