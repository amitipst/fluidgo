"""Contacts master (v1.4.0-A): contacts, contact_delete_requests, contact_delete_approvals.

Until now a "contact" was free text (`contact_name`) on meetings and leads and
attendee JSON on meetings; no phone or designation existed anywhere. This adds
a real contacts table anchored to accounts, plus the deletion-approval tables
(nobody hard-deletes a contact). See fluidgo-mom-action-governance-design.md
§9 / §9a.

Purely additive. Backfill: every customer attendee on a meeting that has an
account, every meeting.contact_name, and every lead.contact_name whose company
matches an account becomes a contact, de-duplicated per account by
(lower(name), lower(email)). Backfilled rows have no phone, so they are flagged
incomplete=true and are asked for a primary number the first time someone
picks them in a MOM (nothing is blocked retroactively). Each customer attendee
JSON entry also gains a `contact_id` key (extra key only; harmless on
downgrade).

Downgrade drops the three new tables only. Meeting attendee JSON keeps its
extra `contact_id` keys, which nothing else reads.

Revision ID: 0034
Revises: 0033
"""
import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def _split(full: str):
    parts = " ".join((full or "").split()).split(" ")
    first = parts[0] if parts and parts[0] else ""
    last = " ".join(parts[1:]) or None
    return first, last


def upgrade():
    op.create_table(
        'contacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', UUID(as_uuid=True), nullable=False),
        sa.Column('salutation', sa.String(20), nullable=True),
        sa.Column('first_name', sa.String(120), nullable=False),
        sa.Column('last_name', sa.String(120), nullable=True),
        sa.Column('designation', sa.String(150), nullable=True),
        sa.Column('department', sa.String(120), nullable=True),
        sa.Column('reports_to_contact_id', UUID(as_uuid=True), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone_primary', sa.String(30), nullable=True),
        sa.Column('phone_secondary', sa.String(30), nullable=True),
        sa.Column('linkedin_url', sa.String(300), nullable=True),
        sa.Column('is_primary_contact', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('status', sa.String(10), server_default='active', nullable=False),
        sa.Column('do_not_contact', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('incomplete', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('owner_user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_seed', sa.Boolean(), server_default='false', nullable=False),
    )
    op.create_index('ix_contacts_account', 'contacts', ['account_id'])
    op.create_index('ix_contacts_email_lower', 'contacts', [sa.text('lower(email)')])
    op.create_index('ix_contacts_phone_primary', 'contacts', ['phone_primary'])

    op.create_table(
        'contact_delete_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('contact_id', UUID(as_uuid=True), nullable=False),
        sa.Column('requested_by', UUID(as_uuid=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(12), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_cdr_contact', 'contact_delete_requests', ['contact_id'])
    op.create_index('ix_cdr_status', 'contact_delete_requests', ['status'])

    op.create_table(
        'contact_delete_approvals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', UUID(as_uuid=True), nullable=False),
        sa.Column('approver_user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('approver_slot', sa.String(20), nullable=False),
        sa.Column('decision', sa.String(10), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_cda_request', 'contact_delete_approvals', ['request_id'])

    _backfill(op.get_bind())


def _backfill(bind):
    now = datetime.now(timezone.utc)
    seen = {}  # (account_id, lower name) -> [contact id, has_email]

    def add(account_id, full_name, email, designation, created_by, is_seed):
        full_name = " ".join((full_name or "").split())
        if not full_name:
            return None
        email = (email or "").strip() or None
        # Same name on the same account = same person for backfill purposes
        # (rows are flagged incomplete; a user can split/merge later).
        key = (str(account_id), full_name.lower())
        if key in seen:
            cid, has_email = seen[key]
            if email and not has_email:
                bind.execute(sa.text("UPDATE contacts SET email = :em WHERE id = :id"), dict(em=email, id=cid))
                seen[key][1] = True
            return cid
        first, last = _split(full_name)
        cid = uuid.uuid4()
        bind.execute(sa.text(
            "INSERT INTO contacts (id, account_id, first_name, last_name, designation, email, "
            "incomplete, created_by, created_at, updated_at, is_seed) "
            "VALUES (:id, :acc, :fn, :ln, :des, :em, true, :cb, :now, :now, :seed)"),
            dict(id=cid, acc=account_id, fn=first[:120], ln=(last or None) and last[:120],
                 des=(designation or None) and designation[:150], em=email, cb=created_by,
                 now=now, seed=bool(is_seed)))
        seen[key] = [cid, bool(email)]
        return cid

    # 1) meetings: customer attendees + contact_name
    rows = bind.execute(sa.text(
        "SELECT id, account_id, user_id, attendees, contact_name, is_seed FROM meetings "
        "WHERE account_id IS NOT NULL")).fetchall()
    for mid, acc, uid, attendees, contact_name, is_seed in rows:
        changed = False
        att = attendees if isinstance(attendees, list) else (json.loads(attendees) if attendees else [])
        out = []
        for a in att or []:
            a = dict(a)
            is_customer = (a.get("side") == "customer") or (not a.get("side") and a.get("is_external"))
            if is_customer and a.get("name") and not a.get("contact_id"):
                cid = add(acc, a.get("name"), a.get("email"), a.get("title"), uid, is_seed)
                if cid:
                    a["contact_id"] = str(cid)
                    changed = True
            out.append(a)
        if contact_name:
            add(acc, contact_name, None, None, uid, is_seed)
        if changed:
            bind.execute(sa.text("UPDATE meetings SET attendees = CAST(:a AS jsonb) WHERE id = :id"),
                         dict(a=json.dumps(out), id=mid))

    # 2) leads whose company matches an account (case-insensitive)
    leads = bind.execute(sa.text(
        "SELECT l.user_id, l.contact_name, l.is_seed, a.id FROM leads l "
        "JOIN accounts a ON lower(a.name) = lower(trim(l.company)) "
        "WHERE l.contact_name IS NOT NULL AND trim(l.contact_name) <> ''")).fetchall()
    for uid, contact_name, is_seed, acc in leads:
        add(acc, contact_name, None, None, uid, is_seed)


def downgrade():
    # Strip the contact_id links the backfill / API wrote into attendee JSON so
    # a later re-upgrade re-links cleanly instead of leaving dangling ids.
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, attendees FROM meetings WHERE attendees IS NOT NULL "
        "AND attendees::text LIKE '%contact_id%'")).fetchall()
    for mid, att in rows:
        att = att if isinstance(att, list) else json.loads(att)
        for a in att:
            if isinstance(a, dict):
                a.pop("contact_id", None)
        bind.execute(sa.text("UPDATE meetings SET attendees = CAST(:a AS jsonb) WHERE id = :id"),
                     dict(a=json.dumps(att), id=mid))
    op.drop_table('contact_delete_approvals')
    op.drop_table('contact_delete_requests')
    op.drop_table('contacts')
