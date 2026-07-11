"""Fixes a real bug: scoring_results only ever had an INDEX on
(user_id, template_id, period), never a UNIQUE constraint. If any earlier
freeze run raced or double-inserted, duplicate rows exist for the same
period - and fga_approval.py's freeze_period used .scalar_one_or_none(),
which throws MultipleResultsFound (a 500) the moment a duplicate exists.
This migration de-duplicates (keeps the most recently computed row per
group, deletes the rest) THEN adds the missing unique constraint, so the
condition that caused the bug can't recur.

Revision ID: 0019
Revises: 0018
"""
from alembic import op

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade():
    # Keep the most-recently-computed row per (user_id, template_id, period);
    # delete any older duplicates.
    op.execute("""
        DELETE FROM scoring_results a
        USING scoring_results b
        WHERE a.user_id = b.user_id
          AND a.template_id = b.template_id
          AND a.period = b.period
          AND a.computed_at < b.computed_at
    """)
    # Tie-break any exact-same-timestamp duplicates by ctid (kept whichever
    # physical row sorts first) so the unique constraint below can't fail.
    op.execute("""
        DELETE FROM scoring_results a
        USING scoring_results b
        WHERE a.user_id = b.user_id
          AND a.template_id = b.template_id
          AND a.period = b.period
          AND a.computed_at = b.computed_at
          AND a.ctid > b.ctid
    """)
    op.create_unique_constraint(
        'uq_scoring_results_user_template_period', 'scoring_results',
        ['user_id', 'template_id', 'period'],
    )


def downgrade():
    op.drop_constraint('uq_scoring_results_user_template_period', 'scoring_results', type_='unique')
