"""Minutes of Meeting extension -- structured discussion points + revision history.

Extends CSG Phase 2 (migration 0031) per Amit's spec (2026-08-04): minutes
need discussion points with a responsible owner and target date, and an
edit history that governance can see (governance is validate-only -- it
needs to SEE that records get kept current, not edit them; see
deny_governance() usage in meetings.py, migration bb967b7 in the same
branch closes the write-access gap this depends on).

Two different storage shapes for two different data shapes -- see
fluidgo-mom-architecture-lld.md ADR-1/ADR-2 for the full reasoning, summary
here:

  - discussion_points  NEW JSONB column on meetings, same convention as
                        attendees (added in 0031) -- a list of structured
                        rows that live and die with one meeting, never
                        queried across meetings in this feature's scope.
                        [{point, responsibility_side, responsibility_name,
                        target_date, status}]. attendees' own shape also
                        grows (email, side) in this same release, but that
                        is a Pydantic/API-layer change only -- JSONB is
                        schemaless, no DDL needed for it.

  - meeting_mom_revisions  NEW TABLE, deliberately NOT a JSONB column.
                        Append-only, unbounded-growth audit log -- the
                        wrong shape for a column that would otherwise get
                        rewritten (and grow) on every single edit to an
                        already-hot row. meeting_id/actor_id are soft refs,
                        same convention as account_id/dsr_id/dor_id on
                        Meeting itself -- no FK constraint, matches this
                        codebase's established pattern for cross-table
                        references that don't need cascade behavior.

Multi-tenancy note (Amit, 2026-08-04): stays internal-only for now, kept
open for later -- no tenant_id added here or anywhere else yet (nothing in
this schema has one; adding it to one new table alone would be
inconsistent and pointless without enforcement everywhere). This migration
only avoids doing anything that would make a future platform-wide
multi-tenancy pass harder -- soft-refs, no hardcoded org assumptions.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('meetings', sa.Column(
        'discussion_points', postgresql.JSONB(), nullable=True))

    op.create_table(
        'meeting_mom_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text('gen_random_uuid()')),
        sa.Column('meeting_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        # generated | edited | finalized | attendees_updated | discussion_points_updated
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('before', postgresql.JSONB(), nullable=True),
        sa.Column('after', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                   server_default=sa.text('now()'), nullable=False),
    )
    # The one query this table exists to serve: "this meeting's history,
    # newest first" (GET /meetings/{id}/revisions). No other access pattern
    # is needed yet -- see ADR-2, ADR-1's cross-meeting-query concern
    # doesn't apply here, revisions are always fetched per-meeting.
    op.create_index('ix_meeting_mom_revisions_meeting_id',
                     'meeting_mom_revisions', ['meeting_id', 'created_at'])


def downgrade():
    op.drop_index('ix_meeting_mom_revisions_meeting_id', table_name='meeting_mom_revisions')
    op.drop_table('meeting_mom_revisions')
    op.drop_column('meetings', 'discussion_points')
