from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SecurityEvent(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (Index("ix_events_user_timestamp", "user_id", "timestamp"),)


@event.listens_for(SecurityEvent, "before_update")
@event.listens_for(SecurityEvent, "before_delete")
def prevent_event_update(_mapper, _connection, _target):
    raise ValueError("Canonical events are immutable; annotate incident evidence instead")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(40), index=True)
    rule_name: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IncidentAlert(Base):
    __tablename__ = "incident_alerts"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), primary_key=True)


class Evidence(Base):
    __tablename__ = "incident_evidence"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    relevance: Mapped[str] = mapped_column(String(20), default="unreviewed")
    note: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (Index("ix_evidence_incident_event", "incident_id", "event_id", unique=True),)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(500))


class EventEntity(Base):
    __tablename__ = "event_entities"
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    narrative: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100))
    ai_assisted: Mapped[bool] = mapped_column(default=False)
    approved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("incident_evidence.id"), primary_key=True)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("incidents.id"), index=True, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(100))
    actor_type: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(100))
    object_id: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Analysis(Base):
    __tablename__ = "ai_analyses"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    provider: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True, unique=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    total: Mapped[int] = mapped_column(Integer)
    passed: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSON)
