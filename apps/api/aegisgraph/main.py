import json
import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import models as m
from . import services as svc
from .config import settings
from .db import get_db
from .detection import load_rules
from .schema import (
    AnalysisRequest,
    EvidencePatch,
    FindingApproval,
    FindingCreate,
    IncidentPatch,
    NoteCreate,
)

logger = logging.getLogger("aegisgraph.http")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class BoundaryMiddleware:
    """Read bodies once with a real bound, including requests lacking Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope["aegisgraph_request_id"] = request_id
        start = time.monotonic()
        headers = dict(scope.get("headers", []))
        method = scope["method"]
        client = (scope.get("client") or ("", 0))[0]

        async def reject(status: int, message: str):
            response = JSONResponse(
                {"detail": message}, status_code=status, headers={"X-Request-ID": request_id}
            )
            await response(scope, receive, send)

        if not settings.allow_remote_demo and client not in {"127.0.0.1", "::1", "testclient"}:
            return await reject(403, "This demo accepts local connections only")
        if method in {"POST", "PATCH", "PUT", "DELETE"}:
            origin = headers.get(b"origin", b"").decode("latin1")
            if origin and origin not in settings.allowed_origins:
                return await reject(403, "Origin not allowed")
        messages = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            size += len(message.get("body", b""))
            if size > 1_048_576:
                return await reject(413, "Request body too large")
            if message["type"] == "http.disconnect" or not message.get("more_body", False):
                break
        cursor = iter(messages)

        async def replay():
            return next(cursor, {"type": "http.disconnect"})

        status_code = 500

        async def secured_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"] += [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                ]
            await send(message)

        try:
            await self.app(scope, replay, secured_send)
        finally:
            logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": round((time.monotonic() - start) * 1000, 1),
                    }
                )
            )


app = FastAPI(
    title="AegisGraph",
    version="0.1.0",
    description="Local, synthetic Atlas security investigation. No enterprise authentication is implemented.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
app.add_middleware(BoundaryMiddleware)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
)


@app.exception_handler(Exception)
async def safe_error(_request, exc):
    logger.error(json.dumps({"error_type": type(exc).__name__, "message": "request failed"}))
    return JSONResponse(
        status_code=500,
        content={"detail": "Request could not be completed"},
        headers={
            "X-Request-ID": _request.scope.get("aegisgraph_request_id", uuid4().hex),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
        },
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "environment": "synthetic_demo", "authentication": "local_demo_analyst"}


@app.get("/api/overview")
def overview(db: Session = Depends(get_db)):
    incidents = list(
        db.scalars(select(m.Incident).order_by(m.Incident.created_at.desc()).limit(10))
    )

    def count(model):
        return db.scalar(select(func.count()).select_from(model))

    review_required = db.scalar(
        select(func.count())
        .select_from(m.Incident)
        .where(m.Incident.status.in_(["new", "investigating"]))
    )
    return {
        "counts": {
            "events": count(m.SecurityEvent),
            "alerts": count(m.Alert),
            "incidents": count(m.Incident),
            "active_incidents": db.scalar(
                select(func.count()).select_from(m.Incident).where(m.Incident.status != "resolved")
            ),
            "high_incidents": db.scalar(
                select(func.count())
                .select_from(m.Incident)
                .where(m.Incident.severity.in_(["high", "critical"]))
            ),
            "review_required": review_required,
        },
        "incidents": [svc.incident_json(incident, db) for incident in incidents],
        "recent_alerts": [
            svc.alert_json(db, alert)
            for alert in db.scalars(select(m.Alert).order_by(m.Alert.timestamp.desc()).limit(6))
        ],
        "recent_events": [
            event.payload
            for event in db.scalars(
                select(m.SecurityEvent).order_by(m.SecurityEvent.timestamp.desc()).limit(8)
            )
        ],
        "demo": True,
        "analyst": settings.demo_analyst,
    }


@app.get("/api/events")
def events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=1000000),
    q: str | None = Query(None, max_length=200),
    source: str | None = Query(None, max_length=40),
    event_type: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    conditions = []
    if source:
        conditions.append(m.SecurityEvent.source == source)
    if event_type:
        conditions.append(m.SecurityEvent.event_type == event_type)
    if q:
        # Escaped LIKE values plus ORM bind parameters keep search inert.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            or_(
                m.SecurityEvent.id.ilike(f"%{escaped}%", escape="\\"),
                cast(m.SecurityEvent.payload, String).ilike(f"%{escaped}%", escape="\\"),
            )
        )
    query = select(m.SecurityEvent).where(*conditions)
    total = db.scalar(select(func.count()).select_from(m.SecurityEvent).where(*conditions))
    rows = db.scalars(
        query.order_by(m.SecurityEvent.timestamp.desc(), m.SecurityEvent.id)
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [row.payload for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/events/{event_id}")
def event_detail(event_id: str, db: Session = Depends(get_db)):
    event = db.get(m.SecurityEvent, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    return event.payload


@app.get("/api/detections")
def detections(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(m.Alert.rule_id, func.count()).group_by(m.Alert.rule_id)).all())
    return {
        "items": [
            {**rule, "enabled": True, "alert_count": counts.get(rule["id"], 0)}
            for rule in load_rules()
        ]
    }


@app.get("/api/alerts")
def alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(m.Alert).order_by(m.Alert.timestamp.desc()).limit(limit).offset(offset)
    )
    return {
        "items": [svc.alert_json(db, row) for row in rows],
        "total": db.scalar(select(func.count()).select_from(m.Alert)),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/incidents")
def incidents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(m.Incident).order_by(m.Incident.updated_at.desc()).limit(limit).offset(offset)
    )
    return {
        "items": [svc.incident_json(row, db) for row in rows],
        "total": db.scalar(select(func.count()).select_from(m.Incident)),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str, db: Session = Depends(get_db)):
    return svc.detail(db, incident_id)


@app.patch("/api/incidents/{incident_id}")
def update_incident(incident_id: str, payload: IncidentPatch, db: Session = Depends(get_db)):
    return svc.patch_incident(db, incident_id, payload.model_dump(exclude_unset=True))


@app.patch("/api/incidents/{incident_id}/evidence/{evidence_id}")
def update_evidence(
    incident_id: str, evidence_id: str, payload: EvidencePatch, db: Session = Depends(get_db)
):
    return svc.patch_evidence(db, incident_id, evidence_id, payload.model_dump(exclude_unset=True))


@app.post("/api/incidents/{incident_id}/findings", status_code=201)
def add_finding(incident_id: str, payload: FindingCreate, db: Session = Depends(get_db)):
    return svc.create_finding(db, incident_id, payload)


@app.patch("/api/incidents/{incident_id}/findings/{finding_id}")
def review_finding(
    incident_id: str, finding_id: str, payload: FindingApproval, db: Session = Depends(get_db)
):
    return svc.approve_finding(db, incident_id, finding_id, payload.approved)


@app.post("/api/incidents/{incident_id}/notes", status_code=201)
def add_note(incident_id: str, payload: NoteCreate, db: Session = Depends(get_db)):
    return svc.create_note(db, incident_id, payload.text)


@app.post("/api/incidents/{incident_id}/analysis")
def analysis(incident_id: str, payload: AnalysisRequest, db: Session = Depends(get_db)):
    return svc.run_analysis(db, incident_id, payload.question)


@app.get("/api/incidents/{incident_id}/report")
def report(incident_id: str, db: Session = Depends(get_db)):
    return svc.report_json(svc.get_report(db, incident_id))


@app.post("/api/incidents/{incident_id}/report")
def draft_report(incident_id: str, db: Session = Depends(get_db)):
    return svc.generate_report(db, incident_id)


@app.post("/api/incidents/{incident_id}/report/approve")
def approve_report(incident_id: str, db: Session = Depends(get_db)):
    return svc.approve_report(db, incident_id)


@app.get("/api/entities/{entity_id}")
def entity_detail(entity_id: str, db: Session = Depends(get_db)):
    entity = db.get(m.Entity, entity_id)
    if entity is None:
        raise HTTPException(404, "Entity not found")
    events = list(
        db.scalars(
            select(m.SecurityEvent)
            .join(m.EventEntity)
            .where(m.EventEntity.entity_id == entity_id)
            .order_by(m.SecurityEvent.timestamp.desc())
            .limit(100)
        )
    )
    return {
        "id": entity.id,
        "type": entity.type,
        "label": entity.label,
        "events": [event.payload for event in events],
        "limit": 100,
    }


@app.get("/api/evaluations")
def evaluations(db: Session = Depends(get_db)):
    run = db.scalar(select(m.EvaluationRun).order_by(m.EvaluationRun.created_at.desc()).limit(1))
    return (
        {**run.result, "id": run.id, "created_at": svc.iso(run.created_at)}
        if run
        else {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "cases": [],
            "categories": [],
            "status": "not_run",
            "live_model_tested": False,
        }
    )


@app.post("/api/evaluations/run")
def run_evaluations(db: Session = Depends(get_db)):
    return svc.execute_evaluations(db)
