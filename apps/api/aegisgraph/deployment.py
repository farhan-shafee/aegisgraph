"""Explicit, non-destructive administration for the synthetic public demo."""

import hashlib
import os
from functools import lru_cache

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import models as m
from .config import ROOT, settings
from .db import Base, engine

FLAGSHIP_ID = "INC-fe8fa4b9508c"
EXPECTED_COUNTS = {"events": 4026, "alerts": 10, "incidents": 1, "evidence": 26, "entities": 235}
INITIALIZATION_LOCK = 712839105


class InitializationError(Exception):
    """Safe, operator-facing diagnostics without connection details."""


@lru_cache(maxsize=1)
def expected_flagship():
    """Derive the canonical case once per process, retaining no event corpus."""
    from .correlation import correlate
    from .detection import evaluate
    from .generator import generate_events

    events = generate_events(seed=42)
    return next(case for case in correlate(evaluate(events), events) if case.id == FLAGSHIP_ID)


def clean_case_state(db: Session) -> bool:
    case = db.get(m.Incident, FLAGSHIP_ID)
    expected = expected_flagship()
    if case is None or (case.title, case.summary, case.severity, case.status, case.owner) != (
        expected.title,
        expected.summary,
        expected.severity,
        "new",
        None,
    ):
        return False
    evidence = db.scalars(select(m.Evidence)).all()
    expected_evidence = {
        (f"EVD-{hashlib.sha256(f'{FLAGSHIP_ID}:{event_id}'.encode()).hexdigest()[:16]}", event_id)
        for event_id in expected.event_ids
    }
    return {(item.id, item.event_id) for item in evidence} == expected_evidence and all(
        item.incident_id == FLAGSHIP_ID and item.relevance == "unreviewed" and item.note == ""
        for item in evidence
    )


def clean_initialization_audit(db: Session, evaluations: list[m.EvaluationRun]) -> bool:
    # Any extra audit event signals local work, including edits later reverted.
    # Three rows are enough to reject; never load an unbounded audit history.
    rows = db.scalars(select(m.Audit).limit(3)).all()
    if len(evaluations) > 1 or len(rows) != 1 + len(evaluations):
        return False
    seed_audit = [row for row in rows if row.action == "incident_created"]
    if len(seed_audit) != 1:
        return False
    row = seed_audit[0]
    if (
        row.actor != "aegisgraph"
        or row.actor_type != "system"
        or row.incident_id != FLAGSHIP_ID
        or row.object_id != FLAGSHIP_ID
        or row.before is not None
        or row.after
        != {
            "rule_families": ["API", "APP", "AUTH", "IAM", "MFA"],
            "correlation": "same principal, at least 3 rules across 2 families, 30-minute span",
            "severity": expected_flagship().severity,
        }
    ):
        return False
    if evaluations:
        evaluation_audit = [row for row in rows if row.action == "evaluations_executed"]
        if len(evaluation_audit) != 1:
            return False
        row, run = evaluation_audit[0], evaluations[0]
        return (
            row.actor == "aegisgraph"
            and row.actor_type == "system"
            and row.incident_id is None
            and row.object_id == run.id
            and row.before is None
            and row.after == {"total": run.total, "passed": run.passed}
        )
    return True


def dataset_status(db: Session) -> dict:
    """Check fixture presence, not cryptographic integrity or production readiness."""
    models = {
        "events": m.SecurityEvent,
        "alerts": m.Alert,
        "incidents": m.Incident,
        "evidence": m.Evidence,
        "entities": m.Entity,
    }
    counts = {
        name: db.scalar(select(func.count()).select_from(model)) for name, model in models.items()
    }
    core_ready = counts == EXPECTED_COUNTS and clean_case_state(db)
    # A public dataset must not contain a local analyst's saved work or live-provider output.
    saved_work = any(
        db.scalar(select(func.count()).select_from(model))
        for model in (
            m.Finding,
            m.Note,
            m.Analysis,
            m.Report,
            m.RuleVersion,
            m.DetectionRegressionRun,
            m.RuleReview,
            m.RulesetState,
        )
    )
    evaluations = db.scalars(select(m.EvaluationRun).limit(2)).all()
    core_ready = core_ready and clean_initialization_audit(db, evaluations)
    from .evaluations import load_fixtures

    fixture_total = len(load_fixtures()["cases"])
    evaluation_ready = len(evaluations) == 1 and all(
        run.total == fixture_total
        and run.passed == fixture_total
        and run.result.get("provider") == "deterministic"
        for run in evaluations
    )
    ready = core_ready and not saved_work and evaluation_ready
    empty = not any(counts.values()) and not any(
        db.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables
    )
    return {
        "ready": ready,
        "status": "ready" if ready else "empty" if empty else "incomplete",
        "counts": counts,
        "core_ready": core_ready and not saved_work,
        "evaluation_runs": len(evaluations),
    }


def require_public_mode() -> None:
    if not settings.public_demo or engine.dialect.name != "postgresql":
        raise InitializationError("This command requires APP_MODE=public_demo and PostgreSQL.")


def initialize_public(*, seed: bool = False) -> dict:
    require_public_mode()
    # One cooperating initialization at a time, including migrations. No destructive reset.
    with engine.connect() as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": INITIALIZATION_LOCK}):
            raise InitializationError("Another public initialization is running. Retry later.")
        try:
            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
            with Session(engine) as db:
                status = dataset_status(db)
                if status["ready"]:
                    return {**status, "action": "unchanged"}
                if not seed:
                    return {**status, "action": "migrated_without_seed"}
                if status["status"] != "empty" and not (
                    status["core_ready"] and status["evaluation_runs"] == 0
                ):
                    raise InitializationError(
                        "Database contains incomplete or non-demo data. No seed or reset performed."
                    )
                from .services import execute_evaluations, seed_database

                if status["status"] == "empty":
                    seed_database(db, seed=42)
                result = execute_evaluations(db)
                if result["failed"]:
                    raise InitializationError(
                        "Deterministic evaluations failed. Demo is not ready."
                    )
                status = dataset_status(db)
                if not status["ready"]:
                    raise InitializationError("Dataset verification failed. Demo is not ready.")
                return {**status, "action": "initialized"}
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": INITIALIZATION_LOCK})


def check_public() -> dict:
    require_public_mode()
    with Session(engine) as db:
        return dataset_status(db)


def serve_public() -> None:
    require_public_mode()
    try:
        port = int(os.environ["PORT"])
        if not 1 <= port <= 65535:
            raise ValueError
    except (KeyError, ValueError):
        raise InitializationError(
            "Public service requires a valid platform-supplied PORT."
        ) from None
    import uvicorn

    # One process preserves the documented in-memory aggregate limits. Hosting terminates TLS.
    # No migrations or seeding at startup, and no raw request paths in access logs.
    uvicorn.run(
        "aegisgraph.main:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        proxy_headers=False,
        access_log=False,
        server_header=False,
        timeout_keep_alive=5,
        limit_concurrency=32,
    )
