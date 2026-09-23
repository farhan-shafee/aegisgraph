import asyncio
import json
import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import models as m
from . import services as svc
from .config import settings
from .corpus_api import router as corpus_router
from .db import get_db
from .export_api import router as export_router
from .hypothesis_api import router as hypothesis_router
from .public_security import PUBLIC_ANALYSIS_PATH, PUBLIC_QUESTIONS, PublicBudget
from .replay_api import router as replay_router
from .rule_api import router as rule_router
from .rule_workflow import effective_rules
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
        self.budget = PublicBudget()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope["aegisgraph_request_id"] = request_id
        start = time.monotonic()
        headers = dict(scope.get("headers", []))
        method = scope["method"]
        client = (scope.get("client") or ("", 0))[0]
        status_code = 500

        async def reject(status: int, message: str, retry_after: int | None = None):
            nonlocal status_code
            status_code = status
            response_headers = {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
            }
            if retry_after is not None:
                response_headers["Retry-After"] = str(retry_after)
            if settings.public_demo and origin in settings.allowed_origins:
                response_headers["Access-Control-Allow-Origin"] = origin
                response_headers["Vary"] = "Origin"
            response = JSONResponse(
                {"detail": message}, status_code=status, headers=response_headers
            )
            await response(scope, receive, send)

        public = settings.public_demo
        path = scope["path"]
        origin = headers.get(b"origin", b"").decode("latin1")
        if (
            not public
            and not settings.allow_remote_demo
            and client not in {"127.0.0.1", "::1", "testclient"}
        ):
            return await reject(403, "This demo accepts local connections only")
        if public:
            if len(path) > 256 or len(scope.get("query_string", b"")) > 2048:
                return await reject(414, "Request URL too long")
            if sum(len(key) + len(value) for key, value in scope.get("headers", [])) > 16384:
                return await reject(431, "Request headers too large")
            if origin and origin not in settings.allowed_origins:
                return await reject(403, "Origin not allowed")
            if method not in {"GET", "HEAD", "OPTIONS"}:
                if method != "POST" or not PUBLIC_ANALYSIS_PATH.fullmatch(path):
                    return await reject(403, "Public demo is read-only; this action is unavailable")
                if origin not in settings.allowed_origins:
                    return await reject(403, "An allowed frontend origin is required")
            if path in {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}:
                return await reject(404, "Not found")
        elif method in {"POST", "PATCH", "PUT", "DELETE"}:
            if origin and origin not in settings.allowed_origins:
                return await reject(403, "Origin not allowed")
        category = PublicBudget.category(method, path)
        if public and (limited := self.budget.enter(category)):
            status, retry = limited
            return await reject(
                status,
                "Demo request budget reached; retry shortly"
                if status == 429
                else "Demo is busy; retry shortly",
                retry,
            )
        response_started = False

        async def secured_send(message):
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
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
            limit = 8192 if public else 1_048_576
            body = bytearray()
            try:
                async with asyncio.timeout(5 if public else None):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > limit:
                            return await reject(413, "Request body too large")
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await reject(408, "Request body timed out")
            replayed = False

            async def replay():
                nonlocal replayed
                if replayed:
                    return {"type": "http.disconnect"}
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, replay, secured_send)
        except Exception as exc:
            if not public:
                raise
            # Handle before Uvicorn sees the exception; never log traceback, SQL,
            # request values, filesystem paths, or credential-bearing URLs.
            logger.error(
                json.dumps({"error_type": type(exc).__name__, "message": "request failed"})
            )
            if not response_started:
                await reject(500, "Request could not be completed")
        finally:
            if public:
                self.budget.leave(category)
            logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": method,
                        **({} if public else {"path": path}),
                        "status": status_code,
                        "duration_ms": round((time.monotonic() - start) * 1000, 1),
                    }
                )
            )


app = FastAPI(
    title="AegisGraph",
    version="0.1.0",
    description="Synthetic Atlas security investigation. No enterprise authentication is implemented.",
    docs_url=None if settings.public_demo else "/docs",
    redoc_url=None if settings.public_demo else "/redoc",
    openapi_url=None if settings.public_demo else "/openapi.json",
)
app.include_router(corpus_router)
app.include_router(replay_router)
app.include_router(rule_router)
app.include_router(hypothesis_router)
app.include_router(export_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=["GET", "HEAD", "POST"] if settings.public_demo else ["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
app.add_middleware(BoundaryMiddleware)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts), www_redirect=False
)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    if settings.public_demo:
        return JSONResponse(status_code=422, content={"detail": "Request input is invalid"})
    return await request_validation_exception_handler(request, exc)


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
    if settings.public_demo:
        return {"status": "ok"}
    return {"status": "ok", "environment": "synthetic_demo", "authentication": "local_demo_analyst"}


@app.get("/ready")
def readiness(db: Session = Depends(get_db)):
    from .deployment import dataset_status

    try:
        ready = dataset_status(db)["ready"]
    except Exception:
        ready = False
    return JSONResponse(
        {"status": "ready" if ready else "not_ready"}, status_code=200 if ready else 503
    )


@app.get("/api/runtime")
def runtime():
    return {
        "app_mode": settings.app_mode,
        "read_only": settings.public_demo,
        "analyst_provider": "deterministic" if settings.public_demo else "configured",
        "questions": list(PUBLIC_QUESTIONS),
        "capabilities": {
            "scenarios": 1,
            "replay": 1,
            "rule_workbench": 1,
            "hypotheses": 1,
            "analyst_benchmark": 1,
            "evidence_bundle": 1,
        },
    }


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
            for rule in effective_rules(db, public_demo=settings.public_demo)
        ],
        "alert_count_scope": "Stored canonical alerts; approving a rule does not rewrite historical alerts.",
    }


@app.get("/api/alerts")
def alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=1000000),
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
    offset: int = Query(0, ge=0, le=1000000),
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
    run = db.scalar(
        select(m.EvaluationRun)
        .where(m.EvaluationRun.result["provider"].as_string() == "deterministic")
        .order_by(m.EvaluationRun.created_at.desc())
        .limit(1)
    )
    return (
        {**run.result, "id": run.id, "created_at": svc.iso(run.created_at)}
        if run
        else {
            "provider": "deterministic",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "cases": [],
            "categories": [],
            "status": "not_run",
            "live_model_tested": False,
        }
    )


@app.get("/api/evaluations/benchmark")
def analyst_benchmark(request: Request):
    if request.query_params:
        raise HTTPException(422, "This benchmark does not accept query parameters")
    from .analyst_benchmark import get_benchmark

    return get_benchmark()


@app.get("/api/evaluations/live")
def live_evaluations(db: Session = Depends(get_db)):
    run = db.scalar(
        select(m.EvaluationRun)
        .where(m.EvaluationRun.result["provider"].as_string() == "openai")
        .order_by(m.EvaluationRun.created_at.desc())
        .limit(1)
    )
    return (
        {**run.result, "id": run.id, "created_at": svc.iso(run.created_at)}
        if run
        else {
            "provider": "openai",
            "run_kind": "live",
            "status": "not_run",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "cases": [],
            "categories": [],
            "live_model_tested": False,
        }
    )


@app.post("/api/evaluations/run")
def run_evaluations(db: Session = Depends(get_db)):
    return svc.execute_evaluations(db)
