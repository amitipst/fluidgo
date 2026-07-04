import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text, Date, SmallInteger
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
    bu:           Mapped[str]        = mapped_column(String(50), default="West")
    business:     Mapped[str]        = mapped_column(String(50), default="fluidpro")
    manager_id:   Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active:    Mapped[bool]       = mapped_column(Boolean, default=True)
    org_role_key: Mapped[str]        = mapped_column(String(30), nullable=True)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

# ── Role hierarchy ────────────────────────────────────────────────────────────
ROLE_HIERARCHY: dict[str, dict] = {
    "rep":           {"level": 10, "scope": "own"},
    "inside_sales":  {"level": 10, "scope": "own"},
    "pre_sales":     {"level": 10, "scope": "own"},
    "manager":       {"level": 20, "scope": "team"},
    "bu_head":       {"level": 30, "scope": "bu"},
    "business_head": {"level": 40, "scope": "business"},
    "hr":            {"level": 25, "scope": "hr"},
    "finance":       {"level": 25, "scope": "finance"},
    "ceo":           {"level": 50, "scope": "all"},
    "super_admin":   {"level": 99, "scope": "all"},
}
def role_level(role: str) -> int: return ROLE_HIERARCHY.get(role, {}).get("level", 0)
def can_manage_targets(role: str) -> bool: return role_level(role) >= 20
def can_see_team(role: str) -> bool: return role_level(role) >= 20 or role in ("hr","finance")
def can_see_all_bu(role: str) -> bool: return role_level(role) >= 30
def is_cross_org(role: str) -> bool: return role_level(role) >= 50

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
    status:           Mapped[str]       = mapped_column(String(30), default="new")
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

class OrgRole(Base):
    """Additive org-hierarchy layer. Independent of `users.role` (rep|inside_sales|
    manager|bu_head), which stays untouched for existing auth/require_role() checks."""
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
    config-driven: edit rows here (via /api/scoring/templates), never a Python constant."""
    __tablename__ = "scoring_parameters"
    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK scoring_templates.id (CASCADE)
    name:          Mapped[str]       = mapped_column(String(100), nullable=False)
    weight_pct:    Mapped[float]     = mapped_column(Numeric(5, 2), nullable=False)
    metric_source: Mapped[str]       = mapped_column(String(100), nullable=False)  # key into scoring_engine's metric registry
    calc_type:     Mapped[str]       = mapped_column(String(20), default="pct")
    sort_order:    Mapped[int]       = mapped_column(Integer, default=0)

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
    """Config-driven targets — no hardcoded target values anywhere in code."""
    __tablename__ = "revenue_targets"
    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK users.id
    period:        Mapped[str]       = mapped_column(String(20), nullable=False)
    target_amount: Mapped[float]     = mapped_column(Numeric(12, 2), nullable=False)
    created_at:    Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class AIInsight(Base):
    __tablename__ = "ai_insights"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type:  Mapped[str]       = mapped_column(String(30))
    entity_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    insight_type: Mapped[str]       = mapped_column(String(30))
    content:      Mapped[str]       = mapped_column(Text)
    generated_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
