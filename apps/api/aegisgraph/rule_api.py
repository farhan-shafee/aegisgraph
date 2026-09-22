"""Typed local rule review and finite, repository-owned public comparisons."""

import json
from functools import lru_cache
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from . import config, rule_workflow
from .db import get_db
from .regressions import compare_rulesets
from .rule_specs import baseline_rules, propose_rules

router = APIRouter(prefix="/api", tags=["detection workbench"])
RuleId = Annotated[str, Path(pattern=r"^[A-Z]{2,4}-[0-9]{3}$", max_length=20)]
RevisionId = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]+$", min_length=1, max_length=80)]
_EXAMPLES = {
    "reduce-benign-volume": 1500,
    "unchanged-volume": 1100,
    "miss-service-access": 2200,
}
_EXAMPLE_LOCK = Lock()


def _mode():
    return {"public_demo": config.settings.public_demo}


def _actor():
    return {"actor_label": config.settings.demo_analyst, **_mode()}


@router.get("/detections/{rule_id}/workbench")
def workbench(rule_id: RuleId, db: Session = Depends(get_db)):
    return rule_workflow.get_workbench(db, rule_id, **_mode())


@router.post("/detections/{rule_id}/versions", status_code=201)
def propose(
    rule_id: RuleId,
    payload: rule_workflow.ProposalRequest,
    db: Session = Depends(get_db),
):
    return rule_workflow.propose_revision(db, rule_id, payload, **_actor())


@router.post("/detection-versions/{revision_id}/regressions", status_code=201)
def regression(revision_id: RevisionId, db: Session = Depends(get_db)):
    return rule_workflow.run_regression(db, revision_id, **_actor())


@router.get("/detection-versions/{revision_id}")
def revision_detail(revision_id: RevisionId, db: Session = Depends(get_db)):
    return rule_workflow.get_revision(db, revision_id, **_mode())


@router.post("/detection-versions/{revision_id}/review")
def review(
    revision_id: RevisionId,
    payload: rule_workflow.ReviewRequest,
    db: Session = Depends(get_db),
):
    return rule_workflow.review_revision(db, revision_id, payload, **_actor())


@lru_cache(maxsize=3)
def _example(example_id: str) -> str:
    baseline = baseline_rules()
    proposal = propose_rules(baseline, "APP-002", {"threshold": _EXAMPLES[example_id]})
    result = compare_rulesets(baseline, proposal, "APP-002")
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode()) > 262144:
        raise ValueError("Repository regression example exceeds its response bound")
    return encoded


@router.get("/regressions/examples/{example_id}")
def example(example_id: Annotated[str, Path(min_length=1, max_length=60)], request: Request):
    if request.query_params:
        raise HTTPException(422, "Regression example query parameters are not supported")
    if example_id not in _EXAMPLES:
        raise HTTPException(404, "Regression example not found")
    # The finite cache contains serialized immutable values; single-flight cold
    # computation and fresh decoding prevent duplicated work or shared mutation.
    with _EXAMPLE_LOCK:
        return json.loads(_example(example_id))
