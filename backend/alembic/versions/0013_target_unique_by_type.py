"""Replace uq_revenue_target_user_period with one that includes target_type,
so a user can hold BOTH a revenue and an order_booking target per period.

Revision ID: 0013
Revises: 0012
"""
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

def upgrade():
    # Old constraint blocked a 2nd row per (user, period). Drop it (name may
    # vary; try the known name, ignore if already gone) and add the 3-col one.
    op.execute("ALTER TABLE revenue_targets DROP CONSTRAINT IF EXISTS uq_revenue_target_user_period")
    op.execute("ALTER TABLE revenue_targets DROP CONSTRAINT IF EXISTS uq_revenue_targets_user_period")
    op.create_unique_constraint(
        "uq_revenue_target_user_period_type",
        "revenue_targets",
        ["user_id", "period", "target_type"],
    )

def downgrade():
    op.drop_constraint("uq_revenue_target_user_period_type", "revenue_targets", type_="unique")
    op.create_unique_constraint(
        "uq_revenue_target_user_period",
        "revenue_targets",
        ["user_id", "period"],
    )
