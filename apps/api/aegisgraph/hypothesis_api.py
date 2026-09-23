"""Case-scoped human review and ephemeral completed-scenario inspection."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from . import config, hypothesis_workflow
from .analyst import AnalysisInputError, DeterministicProvider, analyze
from .db import get_db
from .hypotheses import HypothesisInputError, build_ledger, gap_guidance
from .public_security import PUBLIC_QUESTIONS
from .scenario_investigation import scenario_projection

router = APIRouter(prefix="/api", tags=["hypotheses"])
CaseId = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]+$", min_length=1, max_length=80)]
Kind = Annotated[str, Path(pattern=r"^[a-z_]+$", min_length=1, max_length=60)]
ScenarioId = Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]*$", min_length=1, max_length=60)]
_QUESTIONS = dict(zip(("summary", "malware"), PUBLIC_QUESTIONS, strict=True))


def _no_query(request: Request):
    if request.query_params:
        raise HTTPException(422, "Inspection query parameters are not supported")


def _bounded(value: dict) -> dict:
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > 262144:
        raise HTTPException(422, "Inspection result exceeds its response bound")
    return value


@router.get("/incidents/{incident_id}/hypotheses")
def case_ledger(incident_id: CaseId, request: Request, db: Session = Depends(get_db)):
    _no_query(request)
    return hypothesis_workflow.get_ledger(db, incident_id, public_demo=config.settings.public_demo)


@router.get("/incidents/{incident_id}/hypotheses/{kind}/history")
def history(incident_id: CaseId, kind: Kind, request: Request, db: Session = Depends(get_db)):
    _no_query(request)
    return hypothesis_workflow.get_hypothesis_history(
        db, incident_id, kind, public_demo=config.settings.public_demo
    )


@router.post("/incidents/{incident_id}/hypotheses/{kind}/review")
def review(
    incident_id: CaseId,
    kind: Kind,
    payload: hypothesis_workflow.ReviewHypothesisRequest,
    db: Session = Depends(get_db),
):
    return hypothesis_workflow.review_hypothesis(
        db,
        incident_id,
        kind,
        payload,
        actor_label=config.settings.demo_analyst,
        public_demo=config.settings.public_demo,
    )


@router.get("/hypotheses/{kind}/gaps")
def gaps(kind: Kind, request: Request):
    _no_query(request)
    try:
        return _bounded(gap_guidance(kind))
    except (KeyError, HypothesisInputError):
        raise HTTPException(404, "Hypothesis kind not found") from None


def _completed(db: Session, scenario_id: str) -> tuple[dict, dict]:
    projection = scenario_projection(db, scenario_id, public_demo=config.settings.public_demo)
    scope = projection["final_state"]["investigation"]
    metadata = {
        "view": "completed_scenario",
        "scope_id": scope["id"],
        "scope_kind": scope["kind"],
        "read_only": True,
        "provenance": projection["provenance"],
    }
    return scope, metadata


@router.get("/scenarios/{scenario_id}/hypotheses")
def scenario_ledger(scenario_id: ScenarioId, request: Request, db: Session = Depends(get_db)):
    _no_query(request)
    scope, metadata = _completed(db, scenario_id)
    try:
        ledger = build_ledger(
            scope["id"],
            scope["evidence"],
            allowed_scope_ids={scope["id"]},
            **metadata["provenance"],
        )
    except (AnalysisInputError, ValueError):
        raise HTTPException(422, "Hypothesis evidence was rejected") from None
    for row in ledger["items"]:
        row["review"] = {
            "version": 0,
            "status": "open",
            "recorded_status": "open",
            "actor_label": None,
            "reason": None,
            "created_at": None,
            "related_finding_ids": [],
        }
    return _bounded({**ledger, **metadata})


@router.get("/scenarios/{scenario_id}/analysis/{question_id}")
def scenario_analysis(
    scenario_id: ScenarioId,
    question_id: Annotated[str, Path(min_length=1, max_length=30)],
    request: Request,
    db: Session = Depends(get_db),
):
    _no_query(request)
    question = _QUESTIONS.get(question_id)
    if question is None:
        raise HTTPException(404, "Scenario analyst example not found")
    scope, metadata = _completed(db, scenario_id)
    try:
        # Fixture descriptions, classifications and evaluator labels never enter
        # the provider context. This inspection path is deterministic in both modes.
        result = analyze(
            question,
            scope["id"],
            scope["evidence"],
            allowed_incident_ids={scope["id"]},
            provider=DeterministicProvider(),
        )
    except AnalysisInputError:
        raise HTTPException(422, "Analysis evidence was rejected") from None
    return _bounded({**metadata, "analysis": result})
