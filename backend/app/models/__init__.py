import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text, Date, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]        = mapped_column(String(120), nullable=False)
    email:        Mapped[str]        = mapped_column(String(255), unique=True, nullable=False)
    password_hash:Mapped[str]        = mapped_column(Text, nullable=False)
    role:         Mapped[str]        = mapped_column(String(20), nullable=False)  # rep|inside_sales|manager|bu_head
    bu:           Mapped[str]        = mapped_column(String(50), default="West")
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

class AIInsight(Base):
    __tablename__ = "ai_insights"
    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type:  Mapped[str]       = mapped_column(String(30))
    entity_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    insight_type: Mapped[str]       = mapped_column(String(30))
    content:      Mapped[str]       = mapped_column(Text)
    generated_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
