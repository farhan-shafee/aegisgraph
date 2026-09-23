"""Bounded, human hypothesis review with immutable scoped revision snapshots.

Machine evidence assessments and human decisions remain separate. A stored review
becomes stale whenever its derived evidence or current finding context changes.
The local actor label records provenance; it is not an authentication mechanism.
"""

import copy
import hashlib
import json
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from . import models as m
from . import services as svc
from .hypotheses import HypothesisInputError, build_ledger

KINDS = frozenset(
    (
        "account_compromise",
        "suspicious_privilege_sequence",
        "unapproved_privilege_change",
        "unexplained_bulk_access",
    )
)
MAX_REVISIONS = 20
MAX_EVIDENCE = 80
MAX_FINDINGS = 50
FindingId = Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,80}$")]


class ReviewHypothesisRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, revalidate_instances="always"
    )
    expected_version: StrictInt = Field(ge=0, le=MAX_REVISIONS)
    context_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_status: Literal["open", "accepted", "rejected"]
    related_finding_ids: list[FindingId] = Field(default_factory=list, max_length=10)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_findings(self):
        if len(set(self.related_finding_ids)) != len(self.related_finding_ids):
            raise ValueError("Related finding references must be unique")
        return self


def _kind(kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(404, "Hypothesis not found")


def _incident(db: Session, incident_id: str, *, lock: bool = False) -> m.Incident:
    if lock:
        return svc.lock_incident(db, incident_id)
    statement = select(m.Incident).where(m.Incident.id == incident_id)
    incident = db.scalar(statement.execution_options(populate_existing=True))
    if incident is None:
        raise HTTPException(404, "Incident not found")
    return incident


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _context(db: Session, incident_id: str, *, public_demo: bool) -> tuple[dict, dict[str, dict]]:
    evidence_rows = db.execute(
        select(m.Evidence, m.SecurityEvent)
        .join(m.SecurityEvent, m.SecurityEvent.id == m.Evidence.event_id)
        .where(m.Evidence.incident_id == incident_id)
        .order_by(m.SecurityEvent.timestamp, m.SecurityEvent.id)
        .limit(MAX_EVIDENCE + 1)
        .execution_options(populate_existing=True)
    ).all()
    if len(evidence_rows) > MAX_EVIDENCE:
        raise HTTPException(409, "Hypothesis evidence capacity exceeded")
    evidence = [svc.evidence_json(item, source) for item, source in evidence_rows]
    findings = {}
    if not public_demo:
        finding_rows = db.scalars(
            select(m.Finding)
            .where(m.Finding.incident_id == incident_id)
            .order_by(m.Finding.id)
            .limit(MAX_FINDINGS + 1)
            .execution_options(populate_existing=True)
        ).all()
        if len(finding_rows) > MAX_FINDINGS:
            raise HTTPException(409, "Hypothesis finding capacity exceeded")
        allowed_evidence = {item["id"] for item in evidence}
        for finding in finding_rows:
            references = list(
                db.scalars(
                    select(m.FindingEvidence.evidence_id)
                    .where(m.FindingEvidence.finding_id == finding.id)
                    .order_by(m.FindingEvidence.evidence_id)
                    .limit(MAX_EVIDENCE + 1)
                )
            )
            if len(references) > MAX_EVIDENCE or not set(references).issubset(allowed_evidence):
                raise HTTPException(409, "Finding evidence must belong to this incident")
            findings[finding.id] = {
                "id": finding.id,
                "title": finding.title,
                "narrative": finding.narrative,
                "approved": finding.approved,
                "evidence_ids": references,
            }
    try:
        derived = build_ledger(incident_id, evidence, allowed_scope_ids={incident_id})
        # Annotation/raw changes do not confer factual authority but still invalidate
        # an earlier human review. Include them in the review context, never in AI.
        context_digest = _digest(
            {"derived_ledger": derived, "evidence": evidence, "findings": list(findings.values())}
        )
    except (HypothesisInputError, ValueError, TypeError):
        raise HTTPException(409, "Hypothesis context is invalid") from None
    return {**derived, "context_digest": context_digest, "read_only": public_demo}, findings


def _states(
    db: Session, incident_id: str, ledger: dict
) -> dict[str, tuple[m.HypothesisState, m.HypothesisRevision]]:
    rows = db.scalars(
        select(m.HypothesisState)
        .where(m.HypothesisState.incident_id == incident_id)
        .limit(len(KINDS) + 1)
        .execution_options(populate_existing=True)
    ).all()
    candidates = {item["kind"]: item for item in ledger["items"]}
    if len(rows) > len(KINDS):
        raise HTTPException(409, "Hypothesis review state is invalid")
    result = {}
    for state in rows:
        if state.kind not in candidates or state.id != candidates[state.kind]["id"]:
            raise HTTPException(409, "Hypothesis review state is invalid")
        revision = db.scalar(
            select(m.HypothesisRevision)
            .where(
                m.HypothesisRevision.state_id == state.id,
                m.HypothesisRevision.version == state.current_version,
            )
            .execution_options(populate_existing=True)
        )
        if (
            revision is None
            or revision.snapshot.get("id") != state.id
            or revision.snapshot.get("kind") != state.kind
        ):
            raise HTTPException(409, "Hypothesis review state is invalid")
        result[state.kind] = (state, revision)
    return result


def _review_json(revision: m.HypothesisRevision | None, context_digest: str) -> dict:
    if revision is None:
        return {
            "version": 0,
            "status": "open",
            "recorded_status": "open",
            "actor_label": None,
            "reason": None,
            "related_finding_ids": [],
            "created_at": None,
        }
    return {
        "version": revision.version,
        "status": revision.review_status if revision.context_digest == context_digest else "stale",
        "recorded_status": revision.review_status,
        "actor_label": revision.actor_label,
        "reason": revision.reason,
        "related_finding_ids": copy.deepcopy(revision.related_finding_ids),
        "created_at": svc.iso(revision.created_at),
    }


def get_ledger(db: Session, incident_id: str, *, public_demo: bool) -> dict:
    _incident(db, incident_id)
    result, _ = _context(db, incident_id, public_demo=public_demo)
    states = {} if public_demo else _states(db, incident_id, result)
    for item in result["items"]:
        record = states.get(item["kind"])
        item["review"] = _review_json(record[1] if record else None, result["context_digest"])
    return result


def _revision_json(row: m.HypothesisRevision) -> dict:
    return {
        "id": row.id,
        "state_id": row.state_id,
        "version": row.version,
        "snapshot": copy.deepcopy(row.snapshot),
        "context_digest": row.context_digest,
        "review_status": row.review_status,
        "related_finding_ids": copy.deepcopy(row.related_finding_ids),
        "reason": row.reason,
        "actor_label": row.actor_label,
        "created_at": svc.iso(row.created_at),
    }


def get_hypothesis_history(db: Session, incident_id: str, kind: str, *, public_demo: bool) -> dict:
    if public_demo:
        raise HTTPException(404, "Hypothesis history not found")
    _kind(kind)
    _incident(db, incident_id)
    revisions = db.scalars(
        select(m.HypothesisRevision)
        .join(m.HypothesisState)
        .where(m.HypothesisState.incident_id == incident_id, m.HypothesisState.kind == kind)
        .order_by(m.HypothesisRevision.version.desc())
        .limit(MAX_REVISIONS)
    ).all()
    return {
        "scope_id": incident_id,
        "kind": kind,
        "history": [_revision_json(row) for row in revisions],
    }


def review_hypothesis(
    db: Session,
    incident_id: str,
    kind: str,
    payload: ReviewHypothesisRequest,
    *,
    actor_label: str,
    public_demo: bool,
) -> dict:
    if public_demo:
        raise HTTPException(403, "Public demo is read-only; this action is unavailable")
    if (
        not isinstance(actor_label, str)
        or not 1 <= len(actor_label.strip()) <= 100
        or any(ord(character) < 32 for character in actor_label)
    ):
        raise HTTPException(422, "Analyst label is invalid")
    try:
        payload = ReviewHypothesisRequest.model_validate(payload)
        _kind(kind)
        incident = _incident(db, incident_id, lock=True)
        current, findings = _context(db, incident_id, public_demo=False)
        candidate = next(item for item in current["items"] if item["kind"] == kind)
        prior = _states(db, incident_id, current).get(kind)
        version = prior[0].current_version if prior else 0
        if (
            payload.expected_version != version
            or payload.context_digest != current["context_digest"]
        ):
            raise HTTPException(
                409, "Hypothesis context or review changed; refresh before reviewing"
            )
        if version >= MAX_REVISIONS:
            raise HTTPException(409, "Local hypothesis revision capacity reached")
        if not set(payload.related_finding_ids).issubset(findings):
            raise HTTPException(422, "Related findings must belong to this incident")
        if prior:
            updated = db.execute(
                update(m.HypothesisState)
                .where(
                    m.HypothesisState.id == candidate["id"],
                    m.HypothesisState.current_version == version,
                )
                .values(current_version=version + 1)
                .execution_options(synchronize_session=False)
            )
            if updated.rowcount != 1:
                raise HTTPException(409, "Hypothesis review changed; refresh before reviewing")
        else:
            db.add(
                m.HypothesisState(
                    id=candidate["id"], incident_id=incident_id, kind=kind, current_version=1
                )
            )
        db.flush()
        revision = m.HypothesisRevision(
            id=svc.identifier("HPR"),
            state_id=candidate["id"],
            version=version + 1,
            snapshot=copy.deepcopy(candidate),
            context_digest=current["context_digest"],
            review_status=payload.review_status,
            related_finding_ids=sorted(payload.related_finding_ids),
            reason=payload.reason,
            actor_label=actor_label,
        )
        db.add(revision)
        db.flush()
        db.add(
            m.Audit(
                id=svc.identifier("AUD"),
                incident_id=incident_id,
                actor=actor_label,
                actor_type="human",
                action="hypothesis_reviewed",
                object_id=revision.id,
                before=_review_json(prior[1] if prior else None, current["context_digest"]),
                after={
                    "object_type": "hypothesis_revision",
                    "hypothesis_id": candidate["id"],
                    "kind": kind,
                    "version": version + 1,
                    "review_status": payload.review_status,
                    "epistemic_status": candidate["epistemic_status"],
                    "context_digest": current["context_digest"],
                    "provenance": copy.deepcopy(candidate["provenance"]),
                    "related_finding_ids": sorted(payload.related_finding_ids),
                    "reason": payload.reason,
                },
            )
        )
        svc.invalidate_report(db, incident)
        db.commit()
        return get_ledger(db, incident_id, public_demo=False)
    except Exception as error:
        db.rollback()
        if isinstance(error, IntegrityError):
            raise HTTPException(
                409, "Concurrent hypothesis update; refresh before reviewing"
            ) from None
        if isinstance(error, OperationalError):
            raise HTTPException(503, "Hypothesis workflow is temporarily unavailable") from None
        if isinstance(error, ValidationError):
            raise HTTPException(422, "Hypothesis review input is invalid") from None
        raise
