"""Local, human-reviewed rule snapshots; public readers always use repository rules.

The fixed analyst label is provenance, not authentication. Canonical events and
alerts remain pinned to their original ingestion; approval affects later replay.
"""

import copy
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from . import models as m
from .regressions import compare_rulesets
from .rule_specs import (
    baseline_rules,
    propose_rules,
    rule_parameters,
    ruleset_digest,
    validate_rules,
)
from .services import identifier, iso

MAX_REVISIONS = 100
MAX_RUNS_PER_REVISION = 10
HISTORY_LIMIT = 20


class ProposalRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, revalidate_instances="always"
    )
    parameters: dict[str, StrictInt] = Field(min_length=1, max_length=2)
    base_ruleset_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    base_generation: StrictInt = Field(ge=0)
    base_version: StrictInt = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, revalidate_instances="always"
    )
    decision: Literal["approve", "reject"]
    regression_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,80}$")
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def approval_needs_run(self):
        if self.decision == "approve" and self.regression_id is None:
            raise ValueError("Approval requires a prior regression run")
        return self


def _local_only(public_demo: bool, actor_label: str) -> None:
    if public_demo:
        raise HTTPException(403, "Public demo is read-only; this action is unavailable")
    if (
        not isinstance(actor_label, str)
        or not 1 <= len(actor_label.strip()) <= 100
        or any(ord(char) < 32 for char in actor_label)
    ):
        raise HTTPException(422, "Analyst label is invalid")


def _rule(rules: list[dict], rule_id: str) -> dict:
    result = next((rule for rule in rules if rule["id"] == rule_id), None)
    if result is None:
        raise HTTPException(404, "Detection rule not found")
    return result


def _state(db: Session) -> m.RulesetState | None:
    return db.scalar(
        select(m.RulesetState)
        .where(m.RulesetState.id == 1)
        .execution_options(populate_existing=True)
    )


def _lock_state(db: Session) -> m.RulesetState:
    dialect = db.get_bind().dialect.name
    insert = sqlite_insert if dialect == "sqlite" else pg_insert
    db.execute(
        insert(m.RulesetState)
        .values(id=1, generation=0, active_versions={})
        .on_conflict_do_nothing(index_elements=["id"])
    )
    if dialect == "sqlite":
        # SQLite has no SELECT FOR UPDATE. A no-op write obtains its write lock.
        db.execute(
            update(m.RulesetState)
            .where(m.RulesetState.id == 1)
            .values(generation=m.RulesetState.generation)
        )
    return db.scalar(
        select(m.RulesetState)
        .where(m.RulesetState.id == 1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _effective(db: Session, state: m.RulesetState | None) -> tuple[list[dict], dict[str, int]]:
    rules = baseline_rules()
    versions = {rule["id"]: 1 for rule in rules}
    if state is None or not state.active_versions:
        return rules, versions
    mapping = state.active_versions
    if (
        not isinstance(mapping, dict)
        or not set(mapping).issubset(versions)
        or not all(isinstance(value, str) for value in mapping.values())
    ):
        raise HTTPException(409, "Active ruleset state is invalid")
    rows = db.scalars(
        select(m.RuleVersion)
        .where(m.RuleVersion.id.in_(mapping.values()))
        .execution_options(populate_existing=True)
    ).all()
    approved = set(
        db.scalars(
            select(m.RuleReview.revision_id).where(
                m.RuleReview.revision_id.in_(mapping.values()), m.RuleReview.decision == "approve"
            )
        )
    )
    if len(rows) != len(mapping) or set(mapping.values()) != approved:
        raise HTTPException(409, "Active ruleset state is invalid")
    for row in rows:
        if mapping.get(row.rule_id) != row.id:
            raise HTTPException(409, "Active ruleset state is invalid")
        rules = [
            copy.deepcopy(row.snapshot) if rule["id"] == row.rule_id else rule for rule in rules
        ]
        versions[row.rule_id] = row.version
    try:
        validate_rules(rules)
    except ValueError:
        raise HTTPException(409, "Active ruleset state is invalid") from None
    return rules, versions


def effective_rules(db: Session, *, public_demo: bool) -> list[dict]:
    if public_demo:
        return baseline_rules()
    return _effective(db, _state(db))[0]


def _revision_json(db: Session, revision: m.RuleVersion) -> dict:
    review = db.scalar(select(m.RuleReview).where(m.RuleReview.revision_id == revision.id))
    return {
        "id": revision.id,
        "rule_id": revision.rule_id,
        "version": revision.version,
        "parent_version": revision.parent_version,
        "base_generation": revision.base_generation,
        "base_ruleset_digest": revision.base_ruleset_digest,
        "snapshot": copy.deepcopy(revision.snapshot),
        "reason": revision.reason,
        "actor_label": revision.actor_label,
        "created_at": iso(revision.created_at),
        "status": "proposed"
        if review is None
        else "approved"
        if review.decision == "approve"
        else "rejected",
    }


def get_workbench(db: Session, rule_id: str, *, public_demo: bool) -> dict:
    _rule(baseline_rules(), rule_id)
    state = None if public_demo else _state(db)
    rules, versions = (baseline_rules(), {}) if public_demo else _effective(db, state)
    rule = _rule(rules, rule_id)
    parameters = [{**item, "value": rule[item["name"]]} for item in rule_parameters(rule_id)]
    revisions = (
        []
        if public_demo
        else db.scalars(
            select(m.RuleVersion)
            .where(m.RuleVersion.rule_id == rule_id)
            .order_by(m.RuleVersion.version.desc())
            .limit(HISTORY_LIMIT)
        ).all()
    )
    return {
        "rule": rule,
        "version": versions.get(rule_id, 1),
        "generation": state.generation if state else 0,
        "ruleset_digest": ruleset_digest(rules),
        "parameters": parameters,
        "revisions": [_revision_json(db, row) for row in revisions],
        "revision_count": 0
        if public_demo
        else db.scalar(
            select(func.count()).select_from(m.RuleVersion).where(m.RuleVersion.rule_id == rule_id)
        ),
        "read_only": public_demo,
    }


def _audit(
    db: Session, actor: str, action: str, revision: m.RuleVersion, *, before=None, after=None
):
    db.add(
        m.Audit(
            id=identifier("AUD"),
            incident_id=None,
            actor=actor,
            actor_type="human",
            action=action,
            object_id=revision.id,
            before=before,
            after={
                "object_type": "rule_version",
                "rule_id": revision.rule_id,
                "version": revision.version,
                **(after or {}),
            },
        )
    )


def _write_failure(db: Session, error: Exception):
    db.rollback()
    if isinstance(error, IntegrityError):
        raise HTTPException(409, "Concurrent workflow update; refresh the workbench") from None
    if isinstance(error, OperationalError):
        raise HTTPException(503, "Rule workflow is temporarily unavailable") from None
    if isinstance(error, (ValueError, ValidationError)):
        raise HTTPException(422, "Rule workflow input is invalid") from None
    raise error


def propose_revision(
    db: Session, rule_id: str, payload: ProposalRequest, *, actor_label: str, public_demo: bool
) -> dict:
    _local_only(public_demo, actor_label)
    try:
        payload = ProposalRequest.model_validate(payload)
        _rule(baseline_rules(), rule_id)
        state = _lock_state(db)
        current, versions = _effective(db, state)
        if (state.generation, ruleset_digest(current), versions[rule_id]) != (
            payload.base_generation,
            payload.base_ruleset_digest,
            payload.base_version,
        ):
            raise HTTPException(409, "Ruleset changed; refresh the workbench before proposing")
        if db.scalar(select(func.count()).select_from(m.RuleVersion)) >= MAX_REVISIONS:
            raise HTTPException(409, "Local rule revision capacity reached")
        proposed = propose_rules(current, rule_id, payload.parameters)
        latest = (
            db.scalar(
                select(func.max(m.RuleVersion.version)).where(m.RuleVersion.rule_id == rule_id)
            )
            or 1
        )
        revision = m.RuleVersion(
            id=identifier("REV"),
            rule_id=rule_id,
            version=latest + 1,
            parent_version=versions[rule_id],
            base_generation=state.generation,
            base_ruleset_digest=ruleset_digest(current),
            snapshot=_rule(proposed, rule_id),
            actor_label=actor_label,
            reason=payload.reason,
        )
        db.add(revision)
        db.flush()
        _audit(
            db,
            actor_label,
            "rule_revision_proposed",
            revision,
            before={"parent_version": versions[rule_id], "ruleset_digest": ruleset_digest(current)},
            after={
                "reason": payload.reason,
                "parameters": payload.parameters,
                "generation": state.generation,
            },
        )
        db.commit()
        return _revision_json(db, revision)
    except Exception as error:
        _write_failure(db, error)


def _pending(db: Session, revision_id: str) -> m.RuleVersion:
    row = db.scalar(
        select(m.RuleVersion)
        .where(m.RuleVersion.id == revision_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "Rule revision not found")
    if db.scalar(select(m.RuleReview.id).where(m.RuleReview.revision_id == row.id)):
        raise HTTPException(409, "Rule revision has already been reviewed")
    return row


def _comparison(db: Session, revision: m.RuleVersion, state: m.RulesetState) -> dict:
    current, _ = _effective(db, state)
    if (
        state.generation != revision.base_generation
        or ruleset_digest(current) != revision.base_ruleset_digest
    ):
        raise HTTPException(409, "Ruleset changed; create and evaluate a fresh proposal")
    proposed = [
        copy.deepcopy(revision.snapshot) if rule["id"] == revision.rule_id else rule
        for rule in current
    ]
    return compare_rulesets(current, proposed, revision.rule_id)


def _record_run(
    db: Session, revision: m.RuleVersion, result: dict, actor: str
) -> m.DetectionRegressionRun:
    if (
        db.scalar(
            select(func.count())
            .select_from(m.DetectionRegressionRun)
            .where(m.DetectionRegressionRun.revision_id == revision.id)
        )
        >= MAX_RUNS_PER_REVISION
    ):
        raise HTTPException(409, "Local regression capacity reached for this revision")
    row = m.DetectionRegressionRun(
        id=identifier("RGR"),
        revision_id=revision.id,
        base_ruleset_digest=result["baseline_ruleset_digest"],
        proposed_ruleset_digest=result["proposed_ruleset_digest"],
        corpus_digest=result["corpus_digest"],
        result=result,
        actor_label=actor,
    )
    db.add(row)
    db.flush()
    return row


def _run_json(row: m.DetectionRegressionRun) -> dict:
    return {
        "id": row.id,
        "revision_id": row.revision_id,
        "result": copy.deepcopy(row.result),
        "created_at": iso(row.created_at),
    }


def get_revision(db: Session, revision_id: str, *, public_demo: bool) -> dict:
    """Local history: at most ten bounded corpus results, plus one review record."""
    if public_demo:
        raise HTTPException(404, "Rule revision not found")
    revision = db.get(m.RuleVersion, revision_id)
    if revision is None:
        raise HTTPException(404, "Rule revision not found")
    runs = db.scalars(
        select(m.DetectionRegressionRun)
        .where(m.DetectionRegressionRun.revision_id == revision_id)
        .order_by(m.DetectionRegressionRun.created_at.desc(), m.DetectionRegressionRun.id.desc())
        .limit(MAX_RUNS_PER_REVISION)
    ).all()
    review = db.scalar(select(m.RuleReview).where(m.RuleReview.revision_id == revision_id))
    return {
        "revision": _revision_json(db, revision),
        "runs": [_run_json(row) for row in runs],
        "review": None
        if review is None
        else {
            "id": review.id,
            "decision": review.decision,
            "reason": review.reason,
            "actor_label": review.actor_label,
            "regression_id": review.regression_id,
            "created_at": iso(review.created_at),
        },
    }


def run_regression(db: Session, revision_id: str, *, actor_label: str, public_demo: bool) -> dict:
    _local_only(public_demo, actor_label)
    try:
        state = _lock_state(db)
        revision = _pending(db, revision_id)
        # Reserve one final immutable run for approval's independent recomputation.
        if (
            db.scalar(
                select(func.count())
                .select_from(m.DetectionRegressionRun)
                .where(m.DetectionRegressionRun.revision_id == revision.id)
            )
            >= MAX_RUNS_PER_REVISION - 1
        ):
            raise HTTPException(409, "Local regression capacity reached for this revision")
        result = _comparison(db, revision, state)
        run = _record_run(db, revision, result, actor_label)
        _audit(
            db,
            actor_label,
            "rule_regression_executed",
            revision,
            after={
                "regression_id": run.id,
                "gate": result["gate"]["decision"],
                "corpus_digest": result["corpus_digest"],
                "ruleset_digest": result["proposed_ruleset_digest"],
                "measurement_scope": "synthetic_fixture",
            },
        )
        db.commit()
        return _run_json(run)
    except Exception as error:
        _write_failure(db, error)


def review_revision(
    db: Session, revision_id: str, payload: ReviewRequest, *, actor_label: str, public_demo: bool
) -> dict:
    _local_only(public_demo, actor_label)
    try:
        payload = ReviewRequest.model_validate(payload)
        state = _lock_state(db)
        revision = _pending(db, revision_id)
        prior_run = None
        if payload.regression_id is not None:
            prior_run = db.get(m.DetectionRegressionRun, payload.regression_id)
            if prior_run is None or prior_run.revision_id != revision.id:
                raise HTTPException(422, "Regression run must belong to this revision")
        result, fresh_run = None, None
        old_generation = state.generation
        current_digest = ruleset_digest(_effective(db, state)[0])
        if payload.decision == "approve":
            result = _comparison(db, revision, state)
            if prior_run is None or (
                prior_run.base_ruleset_digest,
                prior_run.proposed_ruleset_digest,
                prior_run.corpus_digest,
            ) != (
                result["baseline_ruleset_digest"],
                result["proposed_ruleset_digest"],
                result["corpus_digest"],
            ):
                raise HTTPException(409, "Regression inputs changed; rerun before review")
            if result["gate"]["decision"] not in {"PASS", "WARN"}:
                raise HTTPException(409, "Proposal blocked by deterministic regression policy")
            if prior_run.result != result:
                raise HTTPException(409, "Regression outcomes changed; rerun before review")
            fresh_run = _record_run(db, revision, result, actor_label)
            active = {**state.active_versions, revision.rule_id: revision.id}
            changed = db.execute(
                update(m.RulesetState)
                .where(
                    m.RulesetState.id == 1, m.RulesetState.generation == revision.base_generation
                )
                .values(generation=revision.base_generation + 1, active_versions=active)
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Ruleset changed; refresh the workbench")
        review = m.RuleReview(
            id=identifier("RRV"),
            revision_id=revision.id,
            decision=payload.decision,
            regression_id=fresh_run.id if fresh_run else payload.regression_id,
            actor_label=actor_label,
            reason=payload.reason,
        )
        db.add(review)
        _audit(
            db,
            actor_label,
            "rule_revision_approved" if payload.decision == "approve" else "rule_revision_rejected",
            revision,
            before={"generation": old_generation, "ruleset_digest": current_digest},
            after={
                "reason": payload.reason,
                "generation": old_generation + int(payload.decision == "approve"),
                "regression_id": review.regression_id,
                "corpus_digest": result["corpus_digest"] if result else None,
                "ruleset_digest": result["proposed_ruleset_digest"] if result else current_digest,
                "proposal_base_ruleset_digest": revision.base_ruleset_digest,
            },
        )
        db.commit()
        return {
            "id": review.id,
            "revision_id": revision.id,
            "decision": review.decision,
            "reason": review.reason,
            "actor_label": review.actor_label,
            "regression_id": review.regression_id,
            "result": result,
            "created_at": iso(review.created_at),
        }
    except Exception as error:
        _write_failure(db, error)
