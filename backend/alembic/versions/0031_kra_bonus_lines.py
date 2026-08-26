"""KRA bonus-line support for the config-driven scoring engine.

Context: scoring_templates/scoring_parameters/manual_metric_entries (see
0003_v2_foundation.py / app/models/__init__.py) already give fluidGo a fully
config-driven, role-based KRA scoring engine — weighted line items, a
tiered-multiplier curve via ScoringParameter.tiers JSONB, and manual entry
for KPIs fluidGo doesn't source itself. It was built ahead of any real KRA
data being loaded, so scoring_templates has zero rows in production today.

This migration adds the one piece that was still missing once real KRA
scorecards (Amit's own July FGA, Hemant's SDM July FGA) were checked against
it: some KRA line items are BONUS lines that add on top of the 100%-weighted
base score rather than being part of the weighted split (e.g. a frontline
"multiple of X% over target" incentive line — uncapped upside, not something
that should ever be required to make weights sum to 100). `is_bonus` marks a
ScoringParameter as one of these; scoring_engine.compute_score adds its
contribution directly to the total instead of folding it into the weighted
100% pool, and the /api/scoring/templates weight-sum validation excludes it.
Purely additive — every existing row defaults to is_bonus=false, i.e. no
behavior change until a template actually sets one.

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('scoring_parameters', sa.Column(
        'is_bonus', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('scoring_parameters', 'is_bonus')
