"""
Audit Log system for fluidGo.
Every user action that mutates data is recorded here.
Queryable by role, user, entity, and time range.
"""
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import uuid
from datetime import datetime


class AuditLog(Base):
    """Immutable audit trail — append-only, never updated or deleted."""
    __tablename__ = "audit_logs"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Who
    user_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_email:  Mapped[str]       = mapped_column(String(255), nullable=False)
    user_role:   Mapped[str]       = mapped_column(String(30), nullable=False)
    user_bu:     Mapped[str]       = mapped_column(String(50), nullable=True)
    # What
    action:      Mapped[str]       = mapped_column(String(50), nullable=False)
    # CREATE | UPDATE | DELETE | LOGIN | LOGOUT | EXPORT | APPROVE | DISPUTE | FREEZE
    entity_type: Mapped[str]       = mapped_column(String(50), nullable=False)
    # dsr | meeting | lead | pipeline | user | fga | incentive | scoring
    entity_id:   Mapped[str]       = mapped_column(String(36), nullable=True)
    # Context
    summary:     Mapped[str]       = mapped_column(String(500), nullable=True)
    diff:        Mapped[dict]      = mapped_column(JSONB, nullable=True)  # {before, after}
    ip_address:  Mapped[str]       = mapped_column(String(45), nullable=True)
    user_agent:  Mapped[str]       = mapped_column(String(500), nullable=True)
    # When
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_user_id",    "user_id"),
        Index("ix_audit_entity",     "entity_type", "entity_id"),
        Index("ix_audit_action",     "action"),
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_bu",         "user_bu"),
    )
