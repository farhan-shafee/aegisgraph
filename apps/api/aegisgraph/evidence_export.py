"""Bounded committed case snapshots for portable, hash-verifiable evidence bundles.

Export is a read operation. It uses a separate repeatable read transaction and does
not flush the caller, acquire write locks, append audit rows, or persist an export.
Public projections omit local human artifacts, including owner and annotations.
"""

import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from time import perf_counter

from fastapi import HTTPException
from sqlalchemy import LargeBinary, Text, cast, func, literal, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, load_only
from sqlalchemy.pool import SingletonThreadPool, StaticPool

from . import models as m
from . import services as svc
from .evidence_bundle import BundleInputError, build_bundle
from .hypotheses import HypothesisInputError, build_ledger
from .hypothesis_workflow import get_ledger

MAX_EVIDENCE = 80
MAX_ALERTS = 80
MAX_FINDINGS = 50
MAX_NOTES = 100
MAX_AUDIT = 1000
# Check text/JSON sizes in SQL before fetching payloads. Four-byte UTF-8 text still
# fits one 256 KiB logical file; the bundle builder enforces exact aggregate bytes.
MAX_FIELD_CHARACTERS = 65536
ATLAS_INCIDENT = "INC-fe8fa4b9508c"
LOGGER = logging.getLogger(__name__)


@contextmanager
def _read_snapshot(db: Session):
    bind = db.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    dialect = engine.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise HTTPException(409, "Evidence export requires a supported snapshot database")
    if dialect == "sqlite" and isinstance(engine.pool, (SingletonThreadPool, StaticPool)):
        # These pools can lend another Session's very same connection, even when
        # this caller has no transaction. Refuse before touching the connection
        # rather than exposing or rolling back any session's uncommitted state.
        raise HTTPException(409, "Evidence export requires an independent read connection")
    with engine.connect() as connection:
        if dialect == "postgresql":
            connection = connection.execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            )
        else:
            # Python's SQLite legacy transaction mode does not BEGIN for SELECT.
            # Explicit BEGIN anchors every following read to one snapshot.
            connection.exec_driver_sql("BEGIN")
        with Session(connection, autoflush=False, expire_on_commit=False) as reader:
            yield reader


def _check_sizes(db: Session, statement, maximum: int, *columns) -> None:
    if not columns:
        return
    bounded = (
        statement.with_only_columns(
            *(
                func.length(cast(column, Text)).label(f"field_size_{index}")
                for index, column in enumerate(columns)
            ),
            maintain_column_froms=True,
        )
        .limit(maximum + 1)
        .subquery()
    )
    if db.scalar(
        select(literal(1))
        .select_from(bounded)
        .where(or_(*(column > MAX_FIELD_CHARACTERS for column in bounded.c)))
        .limit(1)
    ):
        raise HTTPException(409, "Evidence export content capacity exceeded")


def _rows(db: Session, statement, maximum: int, *columns, payload_bytes: int = 256 * 1024):
    _check_sizes(db, statement, maximum, *columns)
    if columns:
        # Bound the combined payload before ORM deserialization. A row cap alone
        # would still permit, for example, 1,000 large audit before/after objects.
        # SQLite stores JSON as text and PostgreSQL serializes JSON on this cast;
        # count their bytes, not Unicode characters. Final bundle encoding remains
        # authoritative for JSON punctuation/escaping and the whole-container cap.
        postgres = db.get_bind().dialect.name == "postgresql"
        sizes = [
            func.coalesce(
                func.octet_length(cast(column, Text))
                if postgres
                else func.length(cast(column, LargeBinary)),
                0,
            )
            for column in columns
        ]
        bounded = (
            statement.with_only_columns(
                sum(sizes).label("payload_bytes"), maintain_column_froms=True
            )
            .limit(maximum + 1)
            .subquery()
        )
        if (db.scalar(select(func.sum(bounded.c.payload_bytes))) or 0) > payload_bytes:
            raise HTTPException(409, "Evidence export content capacity exceeded")
    rows = db.execute(statement.limit(maximum + 1)).all()
    if len(rows) > maximum:
        raise HTTPException(409, "Evidence export collection capacity exceeded")
    return rows


def _references(db: Session, statement, allowed: set[str]) -> list[str]:
    references = [row[0] for row in _rows(db, statement, MAX_EVIDENCE)]
    if not set(references).issubset(allowed):
        raise HTTPException(409, "Evidence export references must belong to this incident")
    return references


def _case_evidence(db: Session, incident_id: str, public_demo: bool) -> list[dict]:
    statement = (
        select(m.Evidence, m.SecurityEvent)
        .join(m.SecurityEvent, m.SecurityEvent.id == m.Evidence.event_id)
        .where(m.Evidence.incident_id == incident_id)
        .order_by(m.SecurityEvent.timestamp, m.SecurityEvent.id)
    )
    if public_demo:
        statement = statement.options(
            load_only(
                m.Evidence.id, m.Evidence.incident_id, m.Evidence.event_id, m.Evidence.relevance
            )
        )
    columns = (
        (m.SecurityEvent.payload,) if public_demo else (m.SecurityEvent.payload, m.Evidence.note)
    )
    return [
        {
            "id": item.id,
            "incident_id": item.incident_id,
            "event_id": item.event_id,
            "timestamp": svc.iso(source.timestamp),
            "relevance": item.relevance,
            "note": "" if public_demo else item.note,
            "event": source.payload,
        }
        for item, source in _rows(
            db, statement, MAX_EVIDENCE, *columns, payload_bytes=2 * 1024 * 1024
        )
    ]


def _case_alerts(db: Session, incident_id: str, event_ids: set[str]) -> list[dict]:
    statement = (
        select(m.Alert)
        .join(m.IncidentAlert, m.IncidentAlert.alert_id == m.Alert.id)
        .where(m.IncidentAlert.incident_id == incident_id)
        .order_by(m.Alert.timestamp, m.Alert.id)
    )
    result = []
    for (row,) in _rows(db, statement, MAX_ALERTS, m.Alert.description):
        references = _references(
            db,
            select(m.AlertEvent.event_id)
            .where(m.AlertEvent.alert_id == row.id)
            .order_by(m.AlertEvent.event_id),
            event_ids,
        )
        result.append(
            {
                "id": row.id,
                "incident_id": incident_id,
                "rule_id": row.rule_id,
                "rule_name": row.rule_name,
                "severity": row.severity,
                "description": row.description,
                "timestamp": svc.iso(row.timestamp),
                "user_id": row.user_id,
                "event_ids": references,
            }
        )
    return result


def _case_findings(db: Session, incident_id: str, evidence_ids: set[str]) -> list[dict]:
    statement = select(m.Finding).where(m.Finding.incident_id == incident_id).order_by(m.Finding.id)
    result = []
    for (row,) in _rows(db, statement, MAX_FINDINGS, m.Finding.narrative):
        references = _references(
            db,
            select(m.FindingEvidence.evidence_id)
            .where(m.FindingEvidence.finding_id == row.id)
            .order_by(m.FindingEvidence.evidence_id),
            evidence_ids,
        )
        result.append(
            {
                "id": row.id,
                "incident_id": incident_id,
                "title": row.title,
                "narrative": row.narrative,
                "author": row.author,
                "ai_assisted": row.ai_assisted,
                "approved": row.approved,
                "created_at": svc.iso(row.created_at),
                "evidence_ids": references,
            }
        )
    return result


def _case_notes(db: Session, incident_id: str) -> list[dict]:
    statement = (
        select(m.Note)
        .where(m.Note.incident_id == incident_id)
        .order_by(m.Note.created_at, m.Note.id)
    )
    return [
        {
            "id": row.id,
            "incident_id": incident_id,
            "text": row.text,
            "author": row.author,
            "created_at": svc.iso(row.created_at),
        }
        for (row,) in _rows(db, statement, MAX_NOTES, m.Note.text)
    ]


def _case_audit(db: Session, incident_id: str) -> list[dict]:
    statement = (
        select(m.Audit)
        .where(m.Audit.incident_id == incident_id)
        .order_by(m.Audit.timestamp, m.Audit.id)
    )
    return [
        {
            "id": row.id,
            "incident_id": incident_id,
            "timestamp": svc.iso(row.timestamp),
            "actor": row.actor,
            "actor_type": row.actor_type,
            "action": row.action,
            "object_id": row.object_id,
            "before": row.before,
            "after": row.after,
        }
        for (row,) in _rows(db, statement, MAX_AUDIT, m.Audit.before, m.Audit.after)
    ]


def _audit_object_scopes(db: Session, incident_id: str, audit: list[dict]) -> None:
    """Check provenance objects omitted from the portable logical-file set.

    The pure builder validates references to included rows. Historical hypothesis
    revisions, reports and analysis records remain in the database, so validate
    only their IDs and case ownership here without reading their private payloads.
    """
    groups = (
        (
            {row["object_id"] for row in audit if row["action"] == "hypothesis_reviewed"},
            select(m.HypothesisRevision.id)
            .join(m.HypothesisState, m.HypothesisState.id == m.HypothesisRevision.state_id)
            .where(m.HypothesisState.incident_id == incident_id),
            m.HypothesisRevision.id,
            80,
        ),
        (
            {
                row["object_id"]
                for row in audit
                if row["action"] in {"report_generated", "report_approved", "report_invalidated"}
            },
            select(m.Report.id).where(m.Report.incident_id == incident_id),
            m.Report.id,
            1,
        ),
        (
            {
                row["object_id"]
                for row in audit
                if row["action"] in {"ai_result_validated", "ai_result_rejected"}
                and row["object_id"] != incident_id
            },
            select(m.Analysis.id).where(m.Analysis.incident_id == incident_id),
            m.Analysis.id,
            MAX_AUDIT,
        ),
    )
    for expected, statement, column, maximum in groups:
        if not expected:
            continue
        actual = {row[0] for row in _rows(db, statement.where(column.in_(expected)), maximum)}
        if actual != expected:
            raise HTTPException(409, "Evidence export audit objects must belong to this incident")


def _case_hypotheses(
    db: Session, incident_id: str, evidence: list[dict], public_demo: bool
) -> dict:
    if public_demo:
        # Use the exact sanitized exported evidence. Neither review state nor
        # local finding context is read or hashed into this public projection.
        return {
            **build_ledger(incident_id, evidence, allowed_scope_ids={incident_id}),
            "read_only": True,
        }
    revisions = (
        select(m.HypothesisRevision.id)
        .join(m.HypothesisState, m.HypothesisState.id == m.HypothesisRevision.state_id)
        .where(
            m.HypothesisState.incident_id == incident_id,
            m.HypothesisRevision.version == m.HypothesisState.current_version,
        )
    )
    _rows(
        db,
        revisions,
        4,
        m.HypothesisRevision.snapshot,
        m.HypothesisRevision.reason,
        m.HypothesisRevision.related_finding_ids,
    )
    return get_ledger(db, incident_id, public_demo=False)


def _snapshot(db: Session, incident_id: str, public_demo: bool) -> dict:
    statement = select(m.Incident).where(m.Incident.id == incident_id)
    if public_demo:
        statement = statement.options(
            load_only(
                m.Incident.id,
                m.Incident.title,
                m.Incident.summary,
                m.Incident.severity,
                m.Incident.status,
                m.Incident.created_at,
                m.Incident.updated_at,
            )
        )
    _check_sizes(db, statement, 1, m.Incident.summary)
    incident = db.scalar(statement)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    if public_demo:
        case = {
            key: getattr(incident, key) for key in ("id", "title", "summary", "severity", "status")
        }
        case.update(
            owner=None,
            created_at=svc.iso(incident.created_at),
            updated_at=svc.iso(incident.updated_at),
        )
    else:
        case = svc.incident_json(incident)
    evidence = _case_evidence(db, incident_id, public_demo)
    alerts = _case_alerts(db, incident_id, {row["event_id"] for row in evidence})
    findings = (
        [] if public_demo else _case_findings(db, incident_id, {row["id"] for row in evidence})
    )
    notes = [] if public_demo else _case_notes(db, incident_id)
    audit = [] if public_demo else _case_audit(db, incident_id)
    if not public_demo:
        _audit_object_scopes(db, incident_id, audit)
    hypotheses = _case_hypotheses(db, incident_id, evidence, public_demo)
    nodes, edges = svc.graph(evidence)
    return {
        "projection": "public_synthetic" if public_demo else "local_review",
        "incident": case,
        "scenario_id": "atlas-compromise" if incident_id == ATLAS_INCIDENT else None,
        "evidence": evidence,
        "alerts": alerts,
        "findings": findings,
        "notes": notes,
        "audit": audit,
        "hypotheses": hypotheses,
        "entities": {"nodes": nodes, "edges": edges},
    }


def export_incident(
    db: Session, incident_id: str, *, public_demo: bool, generated_at: datetime | None = None
) -> dict:
    """Export one committed incident; over-capacity or invalid references fail closed."""
    started = perf_counter()
    try:
        with _read_snapshot(db) as reader:
            snapshot = _snapshot(reader, incident_id, public_demo)
        result = build_bundle(snapshot, generated_at=generated_at or datetime.now(UTC))
    except (BundleInputError, HypothesisInputError, ValueError, TypeError, KeyError):
        raise HTTPException(
            409, "Evidence export snapshot is invalid or exceeds capacity"
        ) from None
    LOGGER.info(
        "Evidence export completed: evidence=%d alerts=%d duration_ms=%.1f",
        len(snapshot["evidence"]),
        len(snapshot["alerts"]),
        (perf_counter() - started) * 1000,
    )
    return result
