import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text, Date, SmallInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.audit import AuditLog  # noqa: F401 — ensure table is registered
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]        = mapped_column(String(120), nullable=False)
    email:        Mapped[str]        = mapped_column(String(255), unique=True, nullable=False)
    password_hash:Mapped[str]        = mapped_column(Text, nullable=False)
    role:         Mapped[str]        = mapped_column(String(30), nullable=False)
    bu:           Mapped[str]        = mapped_column(String(50), default="West")       # legacy — kept for compat
    region:       Mapped[str]        = mapped_column(String(100), nullable=True)       # India - North | India - West | etc.
    business:     Mapped[str]        = mapped_column(String(50), default="fluidpro")  # fluidpro | fluidprint | floxtax | hooks
    manager_id:   Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active:    Mapped[bool]       = mapped_column(Boolean, default=True)
    org_role_key: Mapped[str]        = mapped_column(String(30), nullable=True)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    # ── Password security ─────────────────────────────────────────────────────
    # Set true on every new onboarding (create_user) and every admin-triggered
    # reset (POST /users/{id}/reset-password). Enforced server-side in
    # deps.get_current_user - not just a frontend nag screen - so a user
    # cannot use the app at all until they've set their own password via
    # POST /auth/change-password, which clears this and stamps password_changed_at.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    password_changed_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # FGA doesn't apply to everyone (e.g. someone in a trial period, or a
    # role genuinely outside the scoring model). When set, freeze_period
    # skips this person entirely and HR's BU overview reports them as
    # "Not Applicable" instead of silently missing/incomplete.
    fga_exempt:   Mapped[bool]       = mapped_column(Boolean, default=False, server_default="false", nullable=False)

# ── Role hierarchy ────────────────────────────────────────────────────────────
# "BU" (Business Unit) means a BUSINESS LINE at WEP — fluidpro | fluidprint |
# floxtax | hooks (the `business` column). It does NOT mean a geographic
# region. A "BU Head" therefore heads one entire business line across ALL its
# regions — that's `business_head` below (scope="business"). A person who
# heads just one region WITHIN a business (e.g. India - West, with Managers
# and Reps beneath them) is a `regional_manager` (scope="region") — a
# distinct, more junior tier, not a synonym for BU Head.
ROLE_HIERARCHY: dict[str, dict] = {
    # Field roles — own data only
    "rep":            {"level": 10, "scope": "own"},
    "inside_sales":   {"level": 10, "scope": "own"},
    "pre_sales":      {"level": 10, "scope": "own"},
    # Management roles
    "manager":              {"level": 20, "scope": "team"},
    "service_delivery_manager": {"level": 20, "scope": "team"},  # same tier as manager — a distinct role LABEL so FGA templates and reporting can target it separately, and its reportees (technicians) feed the Resource Attrition KRA
    "hr":                   {"level": 25, "scope": "hr"},
    "finance":               {"level": 25, "scope": "finance"},
    "regional_manager":   {"level": 30, "scope": "region"},   # heads ONE region within ONE business
    # DEPRECATED — old name for regional_manager, kept only so any existing
    # data/integrations using this string keep working. Do not assign this
    # role to new users; use "regional_manager" instead.
    "bu_head":            {"level": 30, "scope": "region"},
    # business_head == practice_head (same level, same scope) — heads ONE
    # business line (fluidpro/fluidprint/floxtax/hooks) across ALL its regions.
    "business_head":  {"level": 40, "scope": "business"},
    "practice_head":  {"level": 40, "scope": "business"},   # alias for business_head
    # COO — above business_head, sees ALL businesses (fluidPro, fluidPrint, floxtax, hooks),
    # not scoped to a single `business` field like business_head is.
    "coo":            {"level": 45, "scope": "all"},
    # Org-wide roles
    "ceo":            {"level": 50, "scope": "all"},
    "super_admin":    {"level": 99, "scope": "all"},
}
def role_level(role: str) -> int: return ROLE_HIERARCHY.get(role, {}).get("level", 0)
def can_manage_targets(role: str) -> bool: return role_level(role) >= 20
def can_see_team(role: str) -> bool: return role_level(role) >= 20 or role in ("hr","finance")
def can_see_all_bu(role: str) -> bool: return role_level(role) >= 30
def is_cross_org(role: str) -> bool: return role_level(role) >= 45

# ── Gamification models ───────────────────────────────────────────────────────
class IncentiveScheme(Base):
    __tablename__ = "incentive_schemes"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bu:           Mapped[str]       = mapped_column(String(50), nullable=False)
    business:     Mapped[str]       = mapped_column(String(50), default="fluidpro")
    scope:        Mapped[str]       = mapped_column(String(20), default="bu")   # team|bu
    name:         Mapped[str]       = mapped_column(String(100), nullable=False)
    description:  Mapped[str]       = mapped_column(Text, nullable=True)
    period:       Mapped[str]       = mapped_column(String(20), nullable=False)
    status:       Mapped[str]       = mapped_column(String(20), default="active")
    metric:       Mapped[str]       = mapped_column(String(50), nullable=False)
    target_value: Mapped[float]     = mapped_column(Numeric(12, 2), nullable=False)
    reward_type:  Mapped[str]       = mapped_column(String(30), nullable=False)
    reward_value: Mapped[float]     = mapped_column(Numeric(10, 2), nullable=True)
    reward_badge: Mapped[str]       = mapped_column(String(50), nullable=True)
    created_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class PointsLedger(Base):
    __tablename__ = "points_ledger"
    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scheme_id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    period:      Mapped[str]       = mapped_column(String(20), nullable=False)
    points:      Mapped[int]       = mapped_column(Integer, nullable=False, default=0)
    reason:      Mapped[str]       = mapped_column(String(200), nullable=True)
    source:      Mapped[str]       = mapped_column(String(50), nullable=True)
    awarded_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class SchemeWinner(Base):
    """One user's achievement of one incentive scheme in one period - the
    validation/payout gate that didn't exist before this: an "achieved"
    scheme was just a boolean computed on the fly (Gamification.tsx's
    progress view), never persisted, and PointsLedger was never actually
    written to by anything despite the model existing. detect_winners()
    in incentives.py is what creates these rows and is what now actually
    credits points/badges. Cash rewards stop at status='pending_hr' until
    HR reviews - real money shouldn't move on an unreviewed auto-computed
    number. Snapshots reward_type/value/badge at detection time so a later
    edit to the scheme doesn't retroactively change what was promised."""
    __tablename__ = "scheme_winners"
    id:             Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id:        Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period:         Mapped[str]       = mapped_column(String(7), nullable=False)
    achieved_value: Mapped[float]     = mapped_column(Numeric(12, 2), nullable=False)
    target_value:   Mapped[float]     = mapped_column(Numeric(12, 2), nullable=False)
    reward_type:    Mapped[str]       = mapped_column(String(20), nullable=False)   # cash|points|badge|recognition
    reward_value:   Mapped[float]     = mapped_column(Numeric(12, 2), nullable=True)
    reward_badge:   Mapped[str]       = mapped_column(String(50), nullable=True)
    # points/badge/recognition are low-stakes and auto-approve on detection;
    # cash requires HR sign-off before it's treated as payable money.
    status:         Mapped[str]       = mapped_column(String(20), default="pending_hr", nullable=False)
    hr_reviewed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    hr_reviewed_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    hr_comment:     Mapped[str]       = mapped_column(String(500), nullable=True)
    paid:           Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    paid_at:        Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at:    Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class UserBadge(Base):
    __tablename__ = "user_badges"
    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    badge_key:   Mapped[str]       = mapped_column(String(50), nullable=False)
    badge_name:  Mapped[str]       = mapped_column(String(100), nullable=False)
    period:      Mapped[str]       = mapped_column(String(20), nullable=True)
    awarded_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class DSRDaily(Base):
    __tablename__ = "dsr_daily"
    id:               Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=False)
    date:             Mapped[datetime]   = mapped_column(Date, nullable=False)
    status:           Mapped[str]        = mapped_column(String(20), default="working")
    dsr_type:         Mapped[str]        = mapped_column(String(20), default="sales")   # sales | presales
    # ── Sales fields ──────────────────────────────────────────────────────────
    visits:           Mapped[int]        = mapped_column(Integer, default=0)
    virtual_meetings: Mapped[int]        = mapped_column(Integer, default=0)
    calls:            Mapped[int]        = mapped_column(Integer, default=0)
    new_leads:        Mapped[int]        = mapped_column(Integer, default=0)
    followups:        Mapped[int]        = mapped_column(Integer, default=0)
    proposals:        Mapped[int]        = mapped_column(Integer, default=0)
    proposal_value:   Mapped[float]      = mapped_column(Numeric(14, 2), nullable=True)
    travel_day:       Mapped[bool]       = mapped_column(Boolean, default=False)
    # ── Pre-Sales fields ──────────────────────────────────────────────────────
    demos_conducted:      Mapped[int]    = mapped_column(Integer, default=0)
    pocs_conducted:       Mapped[int]    = mapped_column(Integer, default=0)
    proposals_supported:  Mapped[int]    = mapped_column(Integer, default=0)
    tech_discussions:     Mapped[int]    = mapped_column(Integer, default=0)
    workshops_conducted:  Mapped[int]    = mapped_column(Integer, default=0)
    trainings_delivered:  Mapped[int]    = mapped_column(Integer, default=0)
    trainings_attended:   Mapped[int]    = mapped_column(Integer, default=0)
    docs_created:         Mapped[int]    = mapped_column(Integer, default=0)
    linked_opportunity_id: Mapped[str]   = mapped_column(String(36), nullable=True)
    # ── Common ────────────────────────────────────────────────────────────────
    notes:            Mapped[str]        = mapped_column(Text, nullable=True)
    submitted_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    # ── Approval workflow ─────────────────────────────────────────────────────
    # draft → submitted → approved | rejected
    # Once 'approved', rep cannot edit. Manager can reject back to 'submitted'.
    approval_status:  Mapped[str]        = mapped_column(String(20), default="submitted")
    approved_by:      Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=True)
    manager_comment:  Mapped[str]        = mapped_column(String(500), nullable=True)
    # ── Post-window edit requests ──────────────────────────────────────────────
    # Self-edit window is 24h from submitted_at. After that (or once approved),
    # a rep can request an exception with a reason; a manager must explicitly
    # grant it (sets edit_granted_until) before editing reopens. Nothing changes
    # after the window without this logged, manager-approved trail.
    edit_request_reason: Mapped[str]      = mapped_column(String(500), nullable=True)
    edit_requested_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    edit_granted_until:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

class SelfScore(Base):
    __tablename__ = "self_scores"
    id:                    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dsr_id:                Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Sales dimensions
    market_coverage:       Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    lead_generation:       Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    followup_discipline:   Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    quality_of_conv:       Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    commitment_to_close:   Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    # Pre-Sales dimensions
    solution_support:      Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    technical_conversion:  Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    knowledge_excellence:  Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    operational_excellence:Mapped[int]       = mapped_column(SmallInteger, nullable=True)

class Meeting(Base):
    __tablename__ = "meetings"
    id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date:             Mapped[datetime]  = mapped_column(Date, nullable=False)
    company:          Mapped[str]       = mapped_column(String(255), nullable=False)
    contact_name:     Mapped[str]       = mapped_column(String(120), nullable=True)
    meeting_type:     Mapped[str]       = mapped_column(String(20))  # F2F|Virtual|Call
    discussion:       Mapped[str]       = mapped_column(Text, nullable=True)
    opportunity:      Mapped[bool]      = mapped_column(Boolean, default=False)
    support_needed:   Mapped[str]       = mapped_column(String(255), nullable=True)
    bant_budget:      Mapped[bool]      = mapped_column(Boolean, nullable=True)
    bant_authority:   Mapped[bool]      = mapped_column(Boolean, nullable=True)
    bant_need:        Mapped[bool]      = mapped_column(Boolean, nullable=True)
    bant_timeline:    Mapped[bool]      = mapped_column(Boolean, nullable=True)
    ai_intent_score:  Mapped[str]       = mapped_column(String(20), nullable=True)
    ai_closure_pct:   Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    ai_recommendation:Mapped[str]       = mapped_column(Text, nullable=True)
    # ── Funnel conversion (meeting → lead) ────────────────────────────────────
    # status: logged → converted. converted_to_lead_id lets the UI show
    # "✓ Converted" instead of offering Convert again, and traces the funnel.
    status:               Mapped[str]       = mapped_column(String(20), default="logged", server_default="logged")
    converted_to_lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at:       Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class Lead(Base):
    __tablename__ = "leads"
    id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date:             Mapped[datetime]  = mapped_column(Date, nullable=False)
    company:          Mapped[str]       = mapped_column(String(255), nullable=False)
    contact_name:     Mapped[str]       = mapped_column(String(120), nullable=True)
    requirement:      Mapped[str]       = mapped_column(Text, nullable=True)
    source:           Mapped[str]       = mapped_column(String(50))
    next_action:      Mapped[str]       = mapped_column(Text, nullable=True)
    next_action_date: Mapped[datetime]  = mapped_column(Date, nullable=True)
    ai_lead_score:    Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    # status: new → qualified → converted (converted = promoted to a pipeline deal)
    status:           Mapped[str]       = mapped_column(String(30), default="new")
    # ── Funnel provenance ─────────────────────────────────────────────────────
    source_meeting_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # meeting this lead came from
    converted_to_deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # deal this lead became
    created_at:       Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class PipelineDeal(Base):
    """Doubles as the 'Opportunity' entity for v2 — extended in place rather than
    duplicated into a parallel table. `company` is the account/customer name and
    `user_id` is the sales owner; both are reused as-is rather than re-added."""
    __tablename__ = "pipeline"
    id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company:          Mapped[str]       = mapped_column(String(255), nullable=False)
    stage:            Mapped[str]       = mapped_column(String(20))
    todays_update:    Mapped[str]       = mapped_column(Text, nullable=True)
    roadblock:        Mapped[bool]      = mapped_column(Boolean, default=False)
    next_step:        Mapped[str]       = mapped_column(Text, nullable=True)
    closure_eta:      Mapped[datetime]  = mapped_column(Date, nullable=True)
    deal_value:       Mapped[float]     = mapped_column(Numeric(12, 2), nullable=True)
    ai_bant_score:    Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    ai_closure_pct:   Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    created_at:       Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at:       Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    # ── v2 Opportunity fields (all nullable — additive, zero risk to existing rows) ──
    bu:               Mapped[str]       = mapped_column(String(50), nullable=True)
    presales_owner_id:Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    primary_contact:  Mapped[str]       = mapped_column(String(120), nullable=True)
    oem:              Mapped[str]       = mapped_column(String(100), nullable=True)
    solution_area:    Mapped[str]       = mapped_column(String(100), nullable=True)  # Managed Services|Cloud|Licensing|Security|Professional Services
    practice:         Mapped[str]       = mapped_column(String(100), nullable=True)
    recurring_revenue:Mapped[float]     = mapped_column(Numeric(12, 2), nullable=True)
    one_time_revenue: Mapped[float]     = mapped_column(Numeric(12, 2), nullable=True)
    gross_margin_pct: Mapped[float]     = mapped_column(Numeric(5, 2), nullable=True)
    competition:      Mapped[str]       = mapped_column(Text, nullable=True)
    risk_level:       Mapped[str]       = mapped_column(String(20), nullable=True)  # low|medium|high|critical
    decision_maker:   Mapped[str]       = mapped_column(String(120), nullable=True)
    budget_status:    Mapped[str]       = mapped_column(String(30), nullable=True)  # confirmed|unconfirmed|unknown
    timeline_status:  Mapped[str]       = mapped_column(String(30), nullable=True)  # on_track|delayed|unknown
    proposal_version: Mapped[str]       = mapped_column(String(20), nullable=True)
    last_activity_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    next_followup_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    ai_deal_health:   Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    ai_deal_health_label: Mapped[str]   = mapped_column(String(30), nullable=True)
    # ── Funnel provenance ─────────────────────────────────────────────────────
    source_lead_id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # lead this deal came from
    # ── Outcome / win-loss analysis ───────────────────────────────────────────
    # Set when a deal is closed as lost/dropped/on_hold. Category is a fixed
    # taxonomy (so losses are analysable in aggregate); detail is free text.
    outcome_category:    Mapped[str]      = mapped_column(String(50), nullable=True)   # e.g. price, competitor, no_decision...
    outcome_detail:      Mapped[str]      = mapped_column(Text, nullable=True)         # rep's free-text explanation
    outcome_competitor:  Mapped[str]      = mapped_column(String(120), nullable=True)  # who won, if lost to competitor
    outcome_recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_ai_analysis: Mapped[str]      = mapped_column(Text, nullable=True)         # AI post-mortem (what went wrong / how to improve)
    # ── Customer Success Governance (CSG) Phase 1 — hunting vs farming ────────
    # deal_type distinguishes net-new pipeline (hunting) from expansion/renewal
    # on an existing account (farming). source records who originated it —
    # 'service_delivery' means it came from an SDM flagging a signal during
    # delivery work (see DORDaily / account_service.get_or_create_account),
    # not from a Sales rep prospecting. account_id is a soft reference (no FK
    # constraint, consistent with manager_id/presales_owner_id elsewhere in
    # this schema) — links this deal to the same persistent Account that
    # Service Delivery's DOR entries reference, so farming signals and
    # delivery reality sit on one timeline per customer.
    deal_type:        Mapped[str]       = mapped_column(String(20), nullable=True, server_default="hunting")  # hunting | farming
    source:           Mapped[str]       = mapped_column(String(20), nullable=True, server_default="sales")     # sales | service_delivery
    account_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    # ── Contract / win-back ───────────────────────────────────────────────────
    # For won deals AND deals lost to a competitor on a fixed-term contract:
    # capture the term so we can resurface the account before the incumbent's
    # contract expires. reengage_at defaults to 4 months before contract_end.
    contract_months:  Mapped[int]       = mapped_column(Integer, nullable=True)        # e.g. 12, 24, 36
    contract_end_date:Mapped[datetime]  = mapped_column(Date, nullable=True)
    reengage_at:      Mapped[datetime]  = mapped_column(Date, nullable=True)           # when to resurface as an alert
    reengage_done:    Mapped[bool]      = mapped_column(Boolean, default=False)        # rep dismissed/actioned the alert
    # ── AI trend analysis over pipeline_updates (on-demand, rep-triggered) ────
    # Verdict cached here so reopening the deal card shows the last check
    # without re-running Ollama; see generate_deal_momentum in pipeline.py.
    ai_momentum_summary:      Mapped[str]      = mapped_column(Text, nullable=True)
    ai_momentum_generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # ── Archive (soft-delete) ──────────────────────────────────────────────
    # Deals never hard-delete — they feed revenue/win-loss/FGA history. For
    # scope="all" roles (ceo/coo/super_admin), resolve_visible_user_ids
    # returns None (no owner filter at all), so dummy/test deals left behind
    # by deactivated accounts were showing up right alongside real data with
    # no way to remove them. archived deals are excluded from every list
    # endpoint by default (all scopes, not just "all"); include_archived=true
    # opts back in for admins who need to see them.
    archived:    Mapped[bool]      = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    archived_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)

class PipelineUpdate(Base):
    """Append-only remark history for a pipeline deal. `todays_update`/`next_step`
    on PipelineDeal itself stay as the current-state snapshot (list view keeps
    working unchanged) — every PATCH that changes todays_update also writes one
    of these rows, so old remarks are never lost. Ordered by created_at this is
    a clean input sequence for AI trend analysis (stall detection, momentum
    summaries) using the same Ollama call pattern as generate_deal_postmortem.
    deal_id/author_id are soft references (no FK constraint), consistent with
    account_id/presales_owner_id on PipelineDeal above."""
    __tablename__ = "pipeline_updates"
    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    update_text:   Mapped[str]       = mapped_column(Text, nullable=False)
    next_step:     Mapped[str]       = mapped_column(Text, nullable=True)
    stage_at_time: Mapped[str]       = mapped_column(String(20), nullable=True)
    created_at:    Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class OrgRole(Base):
    """Additive org-hierarchy layer. Independent of `users.role` (rep|inside_sales|
    manager|regional_manager|business_head), which stays untouched for existing auth/require_role() checks."""
    __tablename__ = "org_roles"
    role_key:         Mapped[str] = mapped_column(String(30), primary_key=True)
    display_name:     Mapped[str] = mapped_column(String(100), nullable=False)
    parent_role_key:  Mapped[str] = mapped_column(String(30), nullable=True)  # FK org_roles.role_key (self)
    data_scope:       Mapped[str] = mapped_column(String(20), nullable=False)  # own|team|bu|practice|all

class ScoringTemplate(Base):
    __tablename__ = "scoring_templates"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]       = mapped_column(String(100), nullable=False)
    role_key:     Mapped[str]       = mapped_column(String(30), nullable=False)  # FK org_roles.role_key
    version:      Mapped[int]       = mapped_column(Integer, default=1)
    is_active:    Mapped[bool]      = mapped_column(Boolean, default=True)
    created_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class ScoringParameter(Base):
    """One weighted line item within a ScoringTemplate — this is what makes weights
    config-driven: edit rows here (via /api/scoring/templates), never a Python constant.

    calc_type='pct'    — value is a straight 0-100 achievement %; contribution =
                          value * (weight_pct/100). Used by Sales/PreSales.
    calc_type='tiered' — value is looked up against `tiers` (a JSON list of bands)
                          to find a MULTIPLIER, and contribution = weight_pct * multiplier
                          (so a strong band can score ABOVE the parameter's base weight,
                          and a weak one can score 0 — matches banded KRA scorecards
                          like Service Delivery's, where >=99% SLA scores 1.5x weight).
                          tiers format: [{"label": "<80%", "max": 80, "multiplier": 0},
                            {"label": ">=80%", "min": 80, "multiplier": null, "formula": "square"}]
                          A tier with "formula":"square" uses multiplier = (value/100)**2
                          instead of a flat number (e.g. "square of achievement").

    metric_source starting with "manual." has no auto-calculator — its value comes
    from ManualMetricEntry (entered via the UI each period) instead of DSR/pipeline
    data, for KPIs sourced from systems fluidGo doesn't integrate with (invoicing,
    ticketing, etc).

    is_active supports enable/disable without losing history — a disabled parameter
    is skipped in scoring but its past ScoringResult breakdowns are untouched."""
    __tablename__ = "scoring_parameters"
    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK scoring_templates.id (CASCADE)
    name:          Mapped[str]       = mapped_column(String(100), nullable=False)
    weight_pct:    Mapped[float]     = mapped_column(Numeric(5, 2), nullable=False)
    metric_source: Mapped[str]       = mapped_column(String(100), nullable=False)  # key into scoring_engine's metric registry, or "manual.<slug>"
    calc_type:     Mapped[str]       = mapped_column(String(20), default="pct")    # pct | tiered
    tiers:         Mapped[list]      = mapped_column(JSONB, nullable=True)         # only for calc_type='tiered'
    is_active:     Mapped[bool]      = mapped_column(Boolean, default=True, server_default="true")
    sort_order:    Mapped[int]       = mapped_column(Integer, default=0)

class ManualMetricEntry(Base):
    """Period achievement value for a 'manual.*' metric_source, entered via UI
    instead of computed from DSR/pipeline data — for KPIs sourced from systems
    fluidGo doesn't integrate with (Tally/Zoho collections, ManageEngine tickets,
    review logs, etc). One row per (user, metric_key, period); upserted on re-entry
    so correcting a mistake doesn't create duplicate history."""
    __tablename__ = "manual_metric_entries"
    id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:     Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=False)
    metric_key:  Mapped[str]        = mapped_column(String(100), nullable=False)  # matches parameter.metric_source
    period:      Mapped[str]        = mapped_column(String(20), nullable=False)
    value:       Mapped[float]      = mapped_column(Numeric(8, 3), nullable=False)  # 0-100 achievement %, or whatever scale the tiers use
    raw_inputs:  Mapped[dict]       = mapped_column(JSONB, nullable=True)  # optional supporting numbers, e.g. {"total_invoiced": 937403.2, "collected": 937403.2}
    notes:       Mapped[str]        = mapped_column(Text, nullable=True)
    entered_by:  Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=False)
    entered_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class DORDaily(Base):
    """Daily Operations Report — Service Delivery Manager's equivalent of DSRDaily.
    Lightweight day-to-day operational log; feeds the Reports section and gives a
    running pulse between monthly FGA cycles. FGA itself is scored from
    ManualMetricEntry period aggregates, not summed from these daily rows — the two
    KRA sets (daily ops vs monthly scorecard) don't share a 1:1 formula, matching
    how DSR activity counts and Sales FGA are related but computed independently."""
    __tablename__ = "dor_daily"
    id:                    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    report_date:           Mapped[Date]      = mapped_column(Date, nullable=False)
    client_account:        Mapped[str]       = mapped_column(String(150), nullable=True)
    account_id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # soft ref → accounts.id, see Account
    status:                Mapped[str]       = mapped_column(String(20), default="on_track")  # on_track | at_risk | critical
    tickets_open_start:    Mapped[int]       = mapped_column(Integer, default=0)
    tickets_new:           Mapped[int]       = mapped_column(Integer, default=0)
    tickets_closed:        Mapped[int]       = mapped_column(Integer, default=0)
    tickets_overdue:       Mapped[int]       = mapped_column(Integer, default=0)   # open >3 days
    escalations_raised:    Mapped[int]       = mapped_column(Integer, default=0)
    escalations_resolved:  Mapped[int]       = mapped_column(Integer, default=0)
    collection_calls_made: Mapped[int]       = mapped_column(Integer, default=0)
    collection_amount:     Mapped[float]     = mapped_column(Numeric(12, 2), nullable=True)
    client_meetings_held:  Mapped[int]       = mapped_column(Integer, default=0)
    resource_deployed:     Mapped[int]       = mapped_column(Integer, nullable=True)
    resource_available:    Mapped[int]       = mapped_column(Integer, nullable=True)
    blockers_notes:        Mapped[str]       = mapped_column(Text, nullable=True)
    submitted_at:          Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    # ── Simple manager approval (no edit-lock/window, unlike DSR) ─────────────
    # Any save resets this to "submitted" (see submit_dor in dor.py), so a
    # rejected entry naturally reappears for review once the SDM resubmits.
    approval_status:       Mapped[str]       = mapped_column(String(20), default="submitted", nullable=False)
    approved_by:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at:            Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    manager_comment:        Mapped[str]       = mapped_column(String(500), nullable=True)

class Account(Base):
    """CSG Phase 1 — the persistent customer identity that Sales pipeline
    (hunting AND farming deals) and Service Delivery (DOR, and future
    meetings/SIP/timeline) both anchor to, instead of each side tracking the
    same customer as a disconnected free-text string. Deliberately minimal
    for Phase 1 — no health score, no relationship owner workflow, no
    timeline aggregation yet; those are Phase 3/4 (see CSG roadmap doc).
    Looked up case-insensitively by (name, business) via
    account_service.get_or_create_account() rather than created directly, so
    "Team Aviation" and "team aviation india pvt ltd" don't silently split
    into two accounts."""
    __tablename__ = "accounts"
    id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:             Mapped[str]       = mapped_column(String(255), nullable=False)
    business:         Mapped[str]       = mapped_column(String(50), default="fluidpro")
    region:           Mapped[str]       = mapped_column(String(100), nullable=True)
    primary_owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # usually the Sales rep/manager who owns this account
    created_at:       Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class ScoringResult(Base):
    """Cached computed score per user/period — with full FGA approval workflow state."""
    __tablename__ = "scoring_results"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_id:  Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period:       Mapped[str]       = mapped_column(String(20), nullable=False)
    score:        Mapped[float]     = mapped_column(Numeric(5, 2), nullable=False)
    breakdown:    Mapped[dict]      = mapped_column(JSONB, nullable=True)
    computed_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    # ── FGA Approval Workflow ─────────────────────────────────────────────────
    # Status lifecycle: pending_manager → pending_hr → pending_vp → approved | disputed
    approval_status:       Mapped[str]        = mapped_column(String(30), nullable=True, default="pending_manager")
    override_score:        Mapped[float]      = mapped_column(Numeric(5, 2), nullable=True)
    manager_comment:       Mapped[str]        = mapped_column(Text, nullable=True)
    hr_comment:            Mapped[str]        = mapped_column(Text, nullable=True)
    vp_comment:            Mapped[str]        = mapped_column(Text, nullable=True)
    reviewed_by_manager_id:Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_by_hr_id:     Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_by_vp_id:     Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=True)
    manager_reviewed_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=True)
    hr_reviewed_at:        Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=True)
    vp_reviewed_at:        Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=True)

class RevenueTarget(Base):
    """Config-driven targets — no hardcoded target values anywhere in code.
    target_type distinguishes revenue vs order-booking targets, both set on
    the same screen by business_head / coo / ceo."""
    __tablename__ = "revenue_targets"
    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK users.id
    period:        Mapped[str]       = mapped_column(String(20), nullable=False)
    target_type:   Mapped[str]       = mapped_column(String(20), default="revenue", server_default="revenue")  # revenue | order_booking
    target_amount: Mapped[float]     = mapped_column(Numeric(12, 2), nullable=False)
    created_at:    Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class AIInsight(Base):
    __tablename__ = "ai_insights"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type:  Mapped[str]       = mapped_column(String(30))
    entity_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    insight_type: Mapped[str]       = mapped_column(String(30))
    content:      Mapped[str]       = mapped_column(Text, nullable=True)
    # pending | ready | failed — supports background generation so nothing
    # ever blocks on a synchronous LLM call. Existing rows default to 'ready'
    # since they were written the old synchronous way and already have content.
    status:       Mapped[str]       = mapped_column(String(20), default="ready", server_default="ready")
    error_detail: Mapped[str]       = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PasswordResetToken(Base):
    """Single-use, time-limited password reset tokens. We store only a SHA-256
    HASH of the token, never the token itself — so a DB leak can't be used to
    reset anyone's password. The raw token goes only into the emailed link."""
    __tablename__ = "password_reset_tokens"
    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str]       = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False)
    used_at:    Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
