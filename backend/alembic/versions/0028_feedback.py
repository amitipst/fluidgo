"""Feedback table — in-app "Report an issue / suggest an idea" capture.

Every logged-in user (any role) can file feedback from anywhere in the app.
It always saves to this table and always alerts super_admin/ceo by email
(reusing the existing SMTP config — see app.services.email_service). Filing
a matching Jira issue is an optional bonus layered on top when JIRA_* env
vars are set (app.config.jira_configured); when they're not set, this table
is the whole system of record and the admin inbox (GET /api/feedback) is
how issues get triaged — zero new tooling required to get started.

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('page_context', sa.String(120), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('jira_issue_key', sa.String(30), nullable=True),
        sa.Column('jira_issue_url', sa.String(255), nullable=True),
        sa.Column('jira_sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_index('ix_feedback_status', 'feedback', ['status'])
    op.create_index('ix_feedback_created_at', 'feedback', ['created_at'])


def downgrade():
    op.drop_index('ix_feedback_created_at', table_name='feedback')
    op.drop_index('ix_feedback_status', table_name='feedback')
    op.drop_table('feedback')
