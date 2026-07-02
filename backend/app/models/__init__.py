import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text, Date, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]        = mapped_column(String(120), nullable=False)
    email:        Mapped[str]        = mapped_column(String(255), unique=True, nullable=False)
    password_hash:Mapped[str]        = mapped_column(Text, nullable=False)
    role:         Mapped[str]        = mapped_column(String(20), nullable=False)  # rep|inside_sales|manager|bu_head
    bu:           Mapped[str]        = mapped_column(String(50), default="West")
    is_active:    Mapped[bool]       = mapped_column(Boolean, default=True)
    # v2: additive org-hierarchy link, independent of `role` above — nothing that reads
    # `role`/require_role() needs to change for this to exist.
    org_role_key: Mapped[str]        = mapped_column(String(30), nullable=True)  # FK org_roles.role_key (declared in migration)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class DSRDaily(Base):
    __tablename__ = "dsr_daily"
    id:               Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), nullable=False)
    date:             Mapped[datetime]   = mapped_column(Date, nullable=False)
    status:           Mapped[str]        = mapped_column(String(20), default="working")
    visits:           Mapped[int]        = mapped_column(Integer, default=0)
    virtual_meetings: Mapped[int]        = mapped_column(Integer, default=0)
    calls:            Mapped[int]        = mapped_column(Integer, default=0)
    new_leads:        Mapped[int]        = mapped_column(Integer, default=0)
    followups:        Mapped[int]        = mapped_column(Integer, default=0)
    proposals:        Mapped[int]        = mapped_column(Integer, default=0)
    notes:            Mapped[str]        = mapped_column(Text, nullable=True)
    submitted_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class SelfScore(Base):
    __tablename__ = "self_scores"
    id:                   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dsr_id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    market_coverage:      Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    lead_generation:      Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    followup_discipline:  Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    quality_of_conv:      Mapped[int]       = mapped_column(SmallInteger, nullable=True)
    commitment_to_close:  Mapped[int]       = mapped_column(SmallInteger, nullable=True)

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
    """Cached computed score per user/period — same caching philosophy as AIInsight."""
    __tablename__ = "scoring_results"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK users.id
    template_id:  Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK scoring_templates.id
    period:       Mapped[str]       = mapped_column(String(20), nullable=False)  # "2026-07" | "2026-Q3" | "2026"
    score:        Mapped[float]     = mapped_column(Numeric(5, 2), nullable=False)
    breakdown:    Mapped[dict]      = mapped_column(JSONB, nullable=True)
    computed_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
