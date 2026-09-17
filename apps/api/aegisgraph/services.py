import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .correlation import correlate
from .detection import evaluate, load_rules
from .generator import generate_events


def identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


def iso(value: datetime | None) -> str | None:
    return (
        value.replace(tzinfo=UTC).isoformat()
        if value and value.tzinfo is None
        else value.isoformat()
        if value
        else None
    )


def audit(
    db: Session,
    incident_id: str | None,
    action: str,
    object_id: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    system: bool = False,
):
    db.add(
        m.Audit(
            id=identifier("AUD"),
            incident_id=incident_id,
            actor="aegisgraph" if system else settings.demo_analyst,
            actor_type="system" if system else "human",
            action=action,
            object_id=object_id,
            before=before,
            after=after,
        )
    )


def require_incident(db: Session, incident_id: str) -> m.Incident:
    incident = db.get(m.Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    return incident


def incident_json(incident: m.Incident, db: Session | None = None) -> dict:
    result = {
        "id": incident.id,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "owner": incident.owner,
        "summary": incident.summary,
        "created_at": iso(incident.created_at),
        "updated_at": iso(incident.updated_at),
    }
    if db is not None:
        result["alert_count"] = db.scalar(
            select(func.count())
            .select_from(m.IncidentAlert)
            .where(m.IncidentAlert.incident_id == incident.id)
        )
        result["evidence_count"] = db.scalar(
            select(func.count())
            .select_from(m.Evidence)
            .where(m.Evidence.incident_id == incident.id)
        )
    return result


def alert_json(db: Session, alert: m.Alert) -> dict:
    return {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "rule_name": alert.rule_name,
        "title": alert.rule_name,
        "severity": alert.severity,
        "description": alert.description,
        "timestamp": iso(alert.timestamp),
        "user_id": alert.user_id,
        "event_ids": list(
            db.scalars(select(m.AlertEvent.event_id).where(m.AlertEvent.alert_id == alert.id))
        ),
        "incident_id": db.scalar(
            select(m.IncidentAlert.incident_id).where(m.IncidentAlert.alert_id == alert.id).limit(1)
        ),
    }


def evidence_for_incident(db: Session, incident_id: str, limit: int = 500) -> list[dict]:
    rows = db.execute(
        select(m.Evidence, m.SecurityEvent)
        .join(m.SecurityEvent, m.SecurityEvent.id == m.Evidence.event_id)
        .where(m.Evidence.incident_id == incident_id)
        .order_by(m.SecurityEvent.timestamp, m.SecurityEvent.id)
        .limit(limit)
    )
    return [evidence_json(evidence, event) for evidence, event in rows]


def evidence_json(evidence: m.Evidence, event: m.SecurityEvent) -> dict:
    return {
        "id": evidence.id,
        "incident_id": evidence.incident_id,
        "event_id": evidence.event_id,
        "timestamp": iso(event.timestamp),
        "relevance": evidence.relevance,
        "note": evidence.note,
        "event": event.payload,
    }


def entity_id(kind: str, value: str) -> str:
    return "ENT-" + hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()[:16]


def extract_entities(event: dict) -> list[dict]:
    values = [
        ("user", event["actor"]["user_id"]),
        ("ip", event["network"]["source_ip"]),
        ("device", event["device"]["device_id"]),
        ("session", event["session"]["session_id"]),
        ("role", event["actor"]["role"]),
        ("service", event["target"]["service"]),
        ("endpoint", event["target"].get("endpoint")),
        ("account", event["target"].get("resource_id")),
    ]
    if event["attributes"].get("new_role"):
        values.append(("role", str(event["attributes"]["new_role"])))
    return list(
        {
            entity_id(kind, value): {"id": entity_id(kind, value), "type": kind, "label": value}
            for kind, value in values
            if value
        }.values()
    )


def graph(evidence: list[dict]) -> tuple[list[dict], list[dict]]:
    entities = {}
    links: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    labels = {
        "ip": "observed from",
        "device": "used device",
        "session": "used session",
        "role": "associated role",
        "service": "accessed service",
        "endpoint": "requested",
        "account": "accessed resource",
    }
    for item in evidence:
        nodes = extract_entities(item["event"])
        principal = next(node["id"] for node in nodes if node["type"] == "user")
        for node in nodes:
            entities[node["id"]] = node
            if node["type"] != "user":
                links[(principal, node["id"], labels[node["type"]])].add(item["id"])
    return list(entities.values()), [
        {"source": source, "target": target, "label": label, "evidence_ids": sorted(ids)}
        for (source, target, label), ids in links.items()
    ]


def finding_json(db: Session, finding: m.Finding) -> dict:
    return {
        "id": finding.id,
        "title": finding.title,
        "narrative": finding.narrative,
        "author": finding.author,
        "ai_assisted": finding.ai_assisted,
        "approved": finding.approved,
        "created_at": iso(finding.created_at),
        "evidence_ids": list(
            db.scalars(
                select(m.FindingEvidence.evidence_id).where(
                    m.FindingEvidence.finding_id == finding.id
                )
            )
        ),
    }


def detail(db: Session, incident_id: str) -> dict:
    incident = require_incident(db, incident_id)
    result = incident_json(incident, db)
    result["evidence"] = evidence_for_incident(db, incident_id)
    result["entities"], result["relationships"] = graph(result["evidence"])
    result["alerts"] = [
        alert_json(db, alert)
        for alert in db.scalars(
            select(m.Alert)
            .join(m.IncidentAlert)
            .where(m.IncidentAlert.incident_id == incident_id)
            .order_by(m.Alert.timestamp)
        )
    ]
    result["findings"] = [
        finding_json(db, finding)
        for finding in db.scalars(
            select(m.Finding)
            .where(m.Finding.incident_id == incident_id)
            .order_by(m.Finding.created_at)
        )
    ]
    result["notes"] = [
        {
            "id": note.id,
            "text": note.text,
            "author": note.author,
            "created_at": iso(note.created_at),
        }
        for note in db.scalars(
            select(m.Note).where(m.Note.incident_id == incident_id).order_by(m.Note.created_at)
        )
    ]
    result["audit"] = [
        {
            "id": row.id,
            "timestamp": iso(row.timestamp),
            "actor": row.actor,
            "actor_type": row.actor_type,
            "action": row.action,
            "object": row.object_id,
            "before": row.before,
            "after": row.after,
        }
        for row in db.scalars(
            select(m.Audit).where(m.Audit.incident_id == incident_id).order_by(m.Audit.timestamp)
        )
    ]
    return result


def invalidate_report(db: Session, incident: m.Incident):
    incident.updated_at = m.utcnow()
    report = db.scalar(select(m.Report).where(m.Report.incident_id == incident.id))
    if report:
        previous = report.status
        report.status = "stale"
        report.approved_at = None
        report.approved_by = None
        if previous != "stale":
            audit(
                db,
                incident.id,
                "report_invalidated",
                report.id,
                before={"status": previous},
                after={"status": "stale"},
                system=True,
            )


def patch_incident(db: Session, incident_id: str, changes: dict) -> dict:
    incident = require_incident(db, incident_id)
    for key, value in changes.items():
        if key in {"status", "severity"} and value is None:
            raise HTTPException(422, f"{key} cannot be null")
        if getattr(incident, key) != value:
            audit(
                db,
                incident_id,
                {
                    "status": "status_changed",
                    "severity": "severity_changed",
                    "owner": "analyst_assigned",
                }[key],
                incident_id,
                before={key: getattr(incident, key)},
                after={key: value},
            )
            setattr(incident, key, value)
    invalidate_report(db, incident)
    db.commit()
    return detail(db, incident_id)


def patch_evidence(db: Session, incident_id: str, evidence_id: str, changes: dict) -> dict:
    incident = require_incident(db, incident_id)
    evidence = db.scalar(
        select(m.Evidence).where(
            m.Evidence.id == evidence_id, m.Evidence.incident_id == incident_id
        )
    )
    if evidence is None:
        raise HTTPException(404, "Evidence not found in this incident")
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Evidence fields cannot be null")
    before = {key: getattr(evidence, key) for key in changes}
    for key, value in changes.items():
        setattr(evidence, key, value)
    audit(db, incident_id, "evidence_annotated", evidence_id, before=before, after=changes)
    invalidate_report(db, incident)
    db.commit()
    return evidence_json(evidence, db.get(m.SecurityEvent, evidence.event_id))


def create_finding(db: Session, incident_id: str, payload) -> dict:
    incident = require_incident(db, incident_id)
    ids = set(payload.evidence_ids)
    allowed = set(db.scalars(select(m.Evidence.id).where(m.Evidence.incident_id == incident_id)))
    if not ids.issubset(allowed):
        raise HTTPException(422, "Finding citations must belong to the current incident")
    finding = m.Finding(
        id=identifier("FND"),
        incident_id=incident_id,
        title=payload.title,
        narrative=payload.narrative,
        author=settings.demo_analyst,
        ai_assisted=payload.ai_assisted,
        approved=payload.approved,
    )
    db.add(finding)
    db.flush()
    db.add_all(m.FindingEvidence(finding_id=finding.id, evidence_id=eid) for eid in sorted(ids))
    audit(
        db,
        incident_id,
        "finding_created",
        finding.id,
        after={
            "approved": finding.approved,
            "ai_assisted": finding.ai_assisted,
            "evidence_ids": sorted(ids),
        },
    )
    invalidate_report(db, incident)
    db.commit()
    return finding_json(db, finding)


def approve_finding(db: Session, incident_id: str, finding_id: str, approved: bool) -> dict:
    incident = require_incident(db, incident_id)
    finding = db.scalar(
        select(m.Finding).where(m.Finding.id == finding_id, m.Finding.incident_id == incident_id)
    )
    if finding is None:
        raise HTTPException(404, "Finding not found")
    audit(
        db,
        incident_id,
        "finding_reviewed",
        finding.id,
        before={"approved": finding.approved},
        after={"approved": approved},
    )
    finding.approved = approved
    invalidate_report(db, incident)
    db.commit()
    return finding_json(db, finding)


def create_note(db: Session, incident_id: str, text: str) -> dict:
    incident = require_incident(db, incident_id)
    note = m.Note(
        id=identifier("NOTE"), incident_id=incident_id, text=text, author=settings.demo_analyst
    )
    db.add(note)
    audit(db, incident_id, "note_created", note.id)
    invalidate_report(db, incident)
    db.commit()
    return {
        "id": note.id,
        "text": note.text,
        "author": note.author,
        "created_at": iso(note.created_at),
    }


def run_analysis(db: Session, incident_id: str, question: str) -> dict:
    from .analyst import AnalysisInputError, analyze

    require_incident(db, incident_id)
    # In the documented single-analyst demo every local case is visible. Model receives only this case.
    allowed = {incident_id}
    evidence = evidence_for_incident(db, incident_id, limit=50)
    audit(
        db,
        incident_id,
        "ai_analysis_requested",
        incident_id,
        after={"evidence_count": len(evidence)},
    )
    db.commit()
    try:
        result = analyze(question, incident_id, evidence, allowed_incident_ids=allowed)
    except AnalysisInputError as exc:
        audit(
            db,
            incident_id,
            "ai_result_rejected",
            incident_id,
            after={"reason": "input_scope_or_validation"},
            system=True,
        )
        db.commit()
        raise HTTPException(422, "Analysis input was rejected") from exc
    analysis = m.Analysis(
        id=identifier("ANA"),
        incident_id=incident_id,
        provider=result["provider"],
        status=result["status"],
        result=result,
    )
    db.add(analysis)
    audit(
        db,
        incident_id,
        "ai_result_rejected"
        if result["status"] in {"rejected", "unavailable"}
        else "ai_result_validated",
        analysis.id,
        after={
            "status": result["status"],
            "provider": result["provider"],
            "context_evidence_count": result["context_evidence_count"],
        },
        system=True,
    )
    db.commit()
    return result


def report_json(report: m.Report) -> dict:
    review_metadata = [
        f"Report status: {report.status}",
        f"Generated: {iso(report.created_at)}",
    ]
    if report.status == "approved":
        review_metadata.append(f"Approved by: {report.approved_by} at {iso(report.approved_at)}")
    elif report.status == "stale":
        review_metadata.append(
            "Review state: stale snapshot; regenerate and review before approval."
        )
    else:
        review_metadata.append("Review state: analyst review required before approval.")
    return {
        "id": report.id,
        "incident_id": report.incident_id,
        "title": report.title,
        "content": "\n".join(review_metadata) + "\n\n" + report.content,
        "status": report.status,
        "created_at": iso(report.created_at),
        "approved_at": iso(report.approved_at),
        "approved_by": report.approved_by,
        "review_required": report.status != "approved",
        "author_type": "deterministic_template",
    }


def generate_report(db: Session, incident_id: str) -> dict:
    case = detail(db, incident_id)
    lines = [
        f"# {case['title']}",
        "",
        "Synthetic Atlas environment · deterministic evidence report · human review required before approval",
        "",
        "## Executive Summary",
        case["summary"],
        "",
        "## Incident Timeline",
    ]
    for item in case["evidence"]:
        event = item["event"]
        lines.append(
            f"- {item['timestamp']} — {event['source']} / {event['action']} / {event['outcome']} [{item['id']}]"
        )
    lines.extend(["", "## Affected Entities"])
    lines.extend(f"- {node['type']}: {node['label']}" for node in case["entities"])
    lines.extend(["", "## Technical Findings"])
    approved = [finding for finding in case["findings"] if finding["approved"]]
    lines.extend(
        f"- {finding['title']}: {finding['narrative']} [{' · '.join(finding['evidence_ids'])}]"
        for finding in approved
    )
    if not approved:
        lines.append("No analyst-approved findings have been recorded.")
    lines.extend(
        [
            "",
            "## Risk / Impact Assessment",
            "Suspicious privileged access merits review. Available telemetry does not establish malware, external exfiltration, or confirmed financial loss.",
            "",
            "## Containment Actions",
            f"Case workflow status: {case['status']}. A status label is not proof of containment. No response actions are executed by this application.",
            "",
            "## Recommended Follow-Up",
            "Validate the role grant and sessions with the account owner. Review access scope. Collect additional identity and endpoint evidence before attributing intent.",
            "",
            "## Evidence Appendix",
        ]
    )
    lines.extend(
        f"- [{item['id']}] event {item['event_id']} · relevance: {item['relevance']}"
        for item in case["evidence"]
    )
    report = db.scalar(select(m.Report).where(m.Report.incident_id == incident_id))
    if report is None:
        report = m.Report(
            id=identifier("RPT"), incident_id=incident_id, title=case["title"], content=""
        )
        db.add(report)
    report.content = "\n".join(lines)
    report.status = "draft"
    report.created_at = m.utcnow()
    report.approved_at = report.approved_by = None
    audit(
        db,
        incident_id,
        "report_generated",
        report.id,
        after={"status": "draft", "source": "deterministic_template"},
    )
    db.commit()
    return report_json(report)


def get_report(db: Session, incident_id: str) -> m.Report:
    require_incident(db, incident_id)
    report = db.scalar(select(m.Report).where(m.Report.incident_id == incident_id))
    if report is None:
        raise HTTPException(404, "Generate a report before viewing or approving it")
    return report


def approve_report(db: Session, incident_id: str) -> dict:
    report = get_report(db, incident_id)
    if report.status == "stale":
        raise HTTPException(
            409, "Incident changed. Generate and review a fresh report before approval."
        )
    report.status = "approved"
    report.approved_at = m.utcnow()
    report.approved_by = settings.demo_analyst
    audit(db, incident_id, "report_approved", report.id, after={"status": "approved"})
    db.commit()
    return report_json(report)


def execute_evaluations(db: Session) -> dict:
    from .evaluations import run_evaluations

    result = run_evaluations()
    run = m.EvaluationRun(
        id=identifier("EVAL"), total=result["total"], passed=result["passed"], result=result
    )
    db.add(run)
    audit(
        db,
        None,
        "evaluations_executed",
        run.id,
        after={"total": result["total"], "passed": result["passed"]},
        system=True,
    )
    db.commit()
    return {**result, "id": run.id, "created_at": iso(run.created_at)}


def seed_database(db: Session, seed: int = 42) -> dict:
    if db.scalar(select(func.count()).select_from(m.SecurityEvent)):
        return {
            "status": "already_seeded",
            "events": db.scalar(select(func.count()).select_from(m.SecurityEvent)),
        }
    events = generate_events(seed=seed)
    entities = {}
    event_entities = []
    for event in events:
        payload = event.model_dump(mode="json")
        db.add(
            m.SecurityEvent(
                id=event.event_id,
                timestamp=event.timestamp,
                source=event.source,
                event_type=event.event_type,
                user_id=event.actor.user_id,
                session_id=event.session.session_id,
                payload=payload,
            )
        )
        for entity in extract_entities(payload):
            entities[entity["id"]] = entity
            event_entities.append(m.EventEntity(event_id=event.event_id, entity_id=entity["id"]))
    db.add_all(m.Entity(**entity) for entity in entities.values())
    db.flush()
    db.add_all(event_entities)
    db.flush()
    signals = evaluate(events)
    for signal in signals:
        db.add(
            m.Alert(
                id=signal.id,
                rule_id=signal.rule_id,
                rule_name=signal.rule_name,
                severity=signal.severity,
                description=signal.description,
                timestamp=datetime.fromisoformat(signal.timestamp),
                user_id=signal.user_id,
            )
        )
    db.flush()
    db.add_all(
        m.AlertEvent(alert_id=signal.id, event_id=eid)
        for signal in signals
        for eid in signal.event_ids
    )
    cases = correlate(signals, events)
    for case in cases:
        db.add(
            m.Incident(
                id=case.id,
                title=case.title,
                severity=case.severity,
                summary=case.summary,
                status="new",
                owner=None,
            )
        )
    db.flush()
    for case in cases:
        db.add_all(m.IncidentAlert(incident_id=case.id, alert_id=aid) for aid in case.alert_ids)
        for event_id in case.event_ids:
            digest = hashlib.sha256(f"{case.id}:{event_id}".encode()).hexdigest()[:16]
            db.add(
                m.Evidence(
                    id=f"EVD-{digest}",
                    incident_id=case.id,
                    event_id=event_id,
                    relevance="unreviewed",
                    note="",
                )
            )
        audit(
            db,
            case.id,
            "incident_created",
            case.id,
            after={
                "rule_families": sorted(
                    {s.rule_id.split("-")[0] for s in signals if s.id in case.alert_ids}
                ),
                "correlation": "same principal, at least 3 rules across 2 families, 30-minute span",
                "severity": case.severity,
            },
            system=True,
        )
    db.commit()
    return {
        "status": "seeded",
        "seed": seed,
        "events": len(events),
        "alerts": len(signals),
        "incidents": len(cases),
        "detections": len(load_rules()),
    }
