"""Local rule revisions require independent regression and explicit human review."""

import importlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from aegisgraph import models as m
from aegisgraph.config import ROOT
from aegisgraph.db import Base, make_engine
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session


def workflow_module():
    try:
        return importlib.import_module("aegisgraph.rule_workflow")
    except ModuleNotFoundError:
        pytest.fail("The local rule revision workflow is not implemented")


@pytest.fixture
def db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def table_rows(db):
    return {
        table.name: list(db.execute(select(table)).mappings())
        for table in Base.metadata.sorted_tables
    }


def test_empty_workbench_reads_do_not_initialize_persistent_state(db):
    workflow = workflow_module()
    before = table_rows(db)
    result = workflow.get_workbench(db, "APP-002", public_demo=False)
    assert result["version"] == 1
    assert result["generation"] == 0
    assert result["rule"]["threshold"] == 1000
    assert result["revisions"] == []
    assert result["revision_count"] == 0
    assert table_rows(db) == before


def test_public_rule_reads_do_not_access_local_workflow_storage():
    workflow = workflow_module()

    class ForbiddenDatabase:
        def __getattr__(self, name):
            pytest.fail("Public rule reads must not inspect local workflow state")

    db = ForbiddenDatabase()
    workbench = workflow.get_workbench(db, "APP-002", public_demo=True)
    assert workbench["version"] == 1
    assert workbench["read_only"] is True
    assert workbench["revisions"] == []
    assert (
        next(
            rule
            for rule in workflow.effective_rules(db, public_demo=True)
            if rule["id"] == "APP-002"
        )["threshold"]
        == 1000
    )


def proposal(db, threshold=1500, rule_id="APP-002", parameters=None):
    workflow = workflow_module()
    current = workflow.get_workbench(db, rule_id, public_demo=False)
    payload = workflow.ProposalRequest(
        parameters=parameters or {"threshold": threshold},
        base_ruleset_digest=current["ruleset_digest"],
        base_generation=current["generation"],
        base_version=current["version"],
        reason="Review the computed synthetic corpus behavior.",
    )
    return workflow.propose_revision(
        db, rule_id, payload, actor_label="demo.analyst", public_demo=False
    )


def regression(db, revision):
    return workflow_module().run_regression(
        db, revision["id"], actor_label="demo.analyst", public_demo=False
    )


def review(db, revision, run, decision="approve"):
    workflow = workflow_module()
    return workflow.review_revision(
        db,
        revision["id"],
        workflow.ReviewRequest(
            decision=decision,
            regression_id=run["id"] if run else None,
            reason="Reviewed synthetic fixture differences and limitations.",
        ),
        actor_label="demo.analyst",
        public_demo=False,
    )


def test_proposal_versions_do_not_replace_effective_rules_without_review(db):
    workflow = workflow_module()
    first = proposal(db)
    second = proposal(db, 1100)
    assert (first["version"], second["version"]) == (2, 3)
    assert first["parent_version"] == second["parent_version"] == 1
    assert first["status"] == second["status"] == "proposed"
    current = workflow.get_workbench(db, "APP-002", public_demo=False)
    assert current["rule"]["threshold"] == 1000
    assert current["revision_count"] == 2
    assert current["generation"] == 0


def test_approval_uses_recomputed_gate_and_changes_only_effective_rules(db):
    workflow = workflow_module()
    revision = proposal(db)
    run = regression(db, revision)
    assert run["result"]["gate"]["decision"] == "PASS"
    accepted = review(db, revision, run)
    assert accepted["decision"] == "approve"
    assert accepted["regression_id"] != run["id"]
    assert db.scalar(select(func.count()).select_from(m.DetectionRegressionRun)) == 2
    current = workflow.get_workbench(db, "APP-002", public_demo=False)
    assert current["version"] == 2
    assert current["generation"] == 1
    assert current["rule"]["threshold"] == 1500
    assert current["revisions"][0]["status"] == "approved"
    assert workflow.get_workbench(db, "APP-002", public_demo=True)["rule"]["threshold"] == 1000
    assert db.scalar(select(func.count()).select_from(m.SecurityEvent)) == 0
    assert db.scalar(select(func.count()).select_from(m.Alert)) == 0
    assert all(
        row.actor == "demo.analyst" and row.actor_type == "human"
        for row in db.scalars(select(m.Audit))
    )
    approval = db.scalar(select(m.Audit).where(m.Audit.action == "rule_revision_approved"))
    assert approval.before["generation"] == 0
    assert approval.after["generation"] == 1
    assert approval.after["object_type"] == "rule_version"
    assert approval.after["reason"]
    assert approval.after["corpus_digest"]


def test_forged_saved_metrics_cannot_bypass_recomputed_block_gate(db):
    revision = proposal(db, 2200)
    run = regression(db, revision)
    assert run["result"]["gate"]["decision"] == "BLOCK"
    # Model-only test deliberately bypasses ORM guards. Migrated databases also
    # reject this direct UPDATE; approval must independently recompute regardless.
    db.execute(
        update(m.DetectionRegressionRun)
        .where(m.DetectionRegressionRun.id == run["id"])
        .values(result={"gate": {"decision": "PASS", "reasons": []}})
    )
    db.commit()
    with pytest.raises(HTTPException) as result:
        review(db, revision, run)
    assert result.value.status_code == 409
    assert workflow_module().get_workbench(db, "APP-002", public_demo=False)["version"] == 1
    assert db.scalar(select(func.count()).select_from(m.RuleReview)) == 0


def test_warn_requires_explicit_review_and_rejection_never_changes_rules(db):
    revision = proposal(db, 1100)
    run = regression(db, revision)
    assert run["result"]["gate"]["decision"] == "WARN"
    accepted = review(db, revision, run)
    assert accepted["decision"] == "approve"
    rejected = proposal(db, 1500)
    assert review(db, rejected, None, "reject")["decision"] == "reject"
    current = workflow_module().get_workbench(db, "APP-002", public_demo=False)
    assert current["rule"]["threshold"] == 1100
    assert current["revisions"][0]["status"] == "rejected"


def test_whole_ruleset_generation_invalidates_other_rule_proposals(db):
    first = proposal(db)
    other = proposal(db, rule_id="MFA-001", parameters={"window_minutes": 4})
    first_run = regression(db, first)
    other_run = regression(db, other)
    review(db, first, first_run)
    with pytest.raises(HTTPException) as result:
        review(db, other, other_run)
    assert result.value.status_code == 409
    assert workflow_module().get_workbench(db, "MFA-001", public_demo=False)["version"] == 1


def test_updated_corpus_requires_a_new_reviewed_run_even_when_rules_are_unchanged(db, monkeypatch):
    workflow = workflow_module()
    revision = proposal(db)
    previous_run = regression(db, revision)
    compare = workflow.compare_rulesets

    def changed_corpus(*args, **kwargs):
        result = compare(*args, **kwargs)
        result["corpus_digest"] = "f" * 64
        return result

    monkeypatch.setattr(workflow, "compare_rulesets", changed_corpus)
    with pytest.raises(HTTPException) as error:
        review(db, revision, previous_run)
    assert error.value.status_code == 409
    assert db.scalar(select(func.count()).select_from(m.RuleReview)) == 0
    fresh_run = regression(db, revision)
    assert review(db, revision, fresh_run)["decision"] == "approve"


def test_rejecting_a_stale_proposal_audits_current_ruleset_and_separate_proposal_base(db):
    workflow = workflow_module()
    first, other = proposal(db), proposal(db, 1100)
    review(db, first, regression(db, first))
    current = workflow.get_workbench(db, "APP-002", public_demo=False)
    review(db, other, None, "reject")
    row = db.scalar(select(m.Audit).where(m.Audit.action == "rule_revision_rejected"))
    assert row.before["generation"] == row.after["generation"] == 1
    assert row.before["ruleset_digest"] == row.after["ruleset_digest"] == current["ruleset_digest"]
    assert row.after["proposal_base_ruleset_digest"] == other["base_ruleset_digest"]
    assert other["base_ruleset_digest"] != current["ruleset_digest"]


def test_changed_computed_outcomes_require_review_even_when_all_input_digests_match(
    db, monkeypatch
):
    workflow = workflow_module()
    revision = proposal(db)
    previous_run = regression(db, revision)
    compare = workflow.compare_rulesets

    def changed_engine(*args, **kwargs):
        result = compare(*args, **kwargs)
        result["metrics"]["after"]["alert_count"] += 1
        return result

    monkeypatch.setattr(workflow, "compare_rulesets", changed_engine)
    with pytest.raises(HTTPException) as error:
        review(db, revision, previous_run)
    assert error.value.status_code == 409
    assert db.scalar(select(func.count()).select_from(m.RuleReview)) == 0
    fresh_run = regression(db, revision)
    assert review(db, revision, fresh_run)["decision"] == "approve"


def test_approval_needs_an_existing_same_revision_run_and_single_review(db):
    workflow = workflow_module()
    first, second = proposal(db), proposal(db, 1100)
    first_run = regression(db, first)
    with pytest.raises(HTTPException) as result:
        review(db, second, first_run)
    assert result.value.status_code == 422
    review(db, first, first_run)
    with pytest.raises(HTTPException) as result:
        review(db, first, first_run)
    assert result.value.status_code == 409
    with pytest.raises(ValidationError):
        workflow.ReviewRequest(decision="approve", reason="Reviewed the proposal")


@pytest.mark.parametrize("bad", [True, "0", -1, 1.5])
def test_proposal_generation_is_a_strict_nonnegative_integer(bad):
    workflow = workflow_module()
    with pytest.raises(ValidationError):
        workflow.ProposalRequest(
            parameters={"threshold": 1500},
            base_ruleset_digest="a" * 64,
            base_generation=bad,
            base_version=1,
            reason="Synthetic threshold review",
        )


def test_public_workflow_mutations_are_refused_before_any_database_access():
    workflow = workflow_module()
    for function, arguments in (
        (workflow.propose_revision, (None, "APP-002", {})),
        (workflow.run_regression, (None, "REV-example")),
        (workflow.review_revision, (None, "REV-example", {})),
    ):
        with pytest.raises(HTTPException) as result:
            function(*arguments, actor_label="demo.analyst", public_demo=True)
        assert result.value.status_code == 403


def test_immutable_revision_run_and_review_models_reject_orm_mutation(db):
    revision = proposal(db)
    run = regression(db, revision)
    reviewed = review(db, revision, None, "reject")
    for model, row_id, field, value in (
        (m.RuleVersion, revision["id"], "reason", "Changed"),
        (m.DetectionRegressionRun, run["id"], "result", {}),
        (m.RuleReview, reviewed["id"], "reason", "Changed"),
    ):
        row = db.get(model, row_id)
        setattr(row, field, value)
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()
        db.delete(db.get(model, row_id))
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()


def test_persisted_revision_detail_survives_a_new_session_and_public_reads_nothing(db):
    workflow = workflow_module()
    revision = proposal(db)
    run = regression(db, revision)
    review(db, revision, run)
    with Session(db.get_bind()) as other:
        before = table_rows(other)
        detail = workflow.get_revision(other, revision["id"], public_demo=False)
        assert detail["revision"]["status"] == "approved"
        assert len(detail["runs"]) == 2
        assert detail["review"]["regression_id"] == detail["runs"][0]["id"]
        assert detail["review"]["reason"]
        assert table_rows(other) == before
    with pytest.raises(HTTPException) as result:
        workflow.get_revision(None, revision["id"], public_demo=True)
    assert result.value.status_code == 404


def test_service_revalidates_modified_request_model_instances(db):
    workflow = workflow_module()
    current = workflow.get_workbench(db, "APP-002", public_demo=False)
    payload = workflow.ProposalRequest(
        parameters={"threshold": 1500},
        base_ruleset_digest=current["ruleset_digest"],
        base_generation=0,
        base_version=1,
        reason="Review fixture result",
    )
    modified = payload.model_copy(update={"base_generation": False})
    with pytest.raises(HTTPException) as result:
        workflow.propose_revision(
            db, "APP-002", modified, actor_label="demo.analyst", public_demo=False
        )
    assert result.value.status_code == 422
    assert db.scalar(select(func.count()).select_from(m.RuleVersion)) == 0


def test_revision_and_regression_caps_are_atomic_and_history_is_bounded(db, monkeypatch):
    workflow = workflow_module()
    monkeypatch.setattr(workflow, "MAX_REVISIONS", 2)
    monkeypatch.setattr(workflow, "HISTORY_LIMIT", 1)
    monkeypatch.setattr(workflow, "MAX_RUNS_PER_REVISION", 3)
    first, second = proposal(db), proposal(db, 1100)
    with pytest.raises(HTTPException) as result:
        proposal(db, 2200)
    assert result.value.status_code == 409
    workbench = workflow.get_workbench(db, "APP-002", public_demo=False)
    assert workbench["revision_count"] == 2
    assert [row["id"] for row in workbench["revisions"]] == [second["id"]]
    run = regression(db, first)
    regression(db, first)
    with pytest.raises(HTTPException) as result:
        regression(db, first)
    assert result.value.status_code == 409
    review(db, first, run)
    assert db.scalar(select(func.count()).select_from(m.DetectionRegressionRun)) == 3


def test_simultaneous_different_rule_approvals_commit_only_one_generation(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'concurrent.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = proposal(db)
        other = proposal(db, rule_id="MFA-001", parameters={"window_minutes": 4})
        first_run, other_run = regression(db, first), regression(db, other)
        assert first_run["result"]["gate"]["decision"] != "BLOCK"
        assert other_run["result"]["gate"]["decision"] != "BLOCK"
    ready = Barrier(2)

    def approve(item):
        revision, run = item
        with Session(engine) as session:
            ready.wait(timeout=10)
            try:
                review(session, revision, run)
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(approve, [(first, first_run), (other, other_run)]))
    assert sorted(statuses) == [200, 409]
    with Session(engine) as db:
        assert db.get(m.RulesetState, 1).generation == 1
        assert len(db.get(m.RulesetState, 1).active_versions) == 1
        assert db.scalar(select(func.count()).select_from(m.RuleReview)) == 1
        assert db.scalar(select(func.count()).select_from(m.DetectionRegressionRun)) == 3
    engine.dispose()


def test_public_readiness_rejects_even_an_otherwise_clean_local_workflow_registry(db):
    from aegisgraph import deployment
    from aegisgraph.services import execute_evaluations, seed_database

    seed_database(db)
    execute_evaluations(db)
    assert deployment.dataset_status(db)["ready"]
    db.add(m.RulesetState(id=1, generation=0, active_versions={}))
    db.commit()
    assert not deployment.dataset_status(db)["ready"]


def migrate(url, revision):
    environment = {
        **os.environ,
        "AEGISGRAPH_LOAD_ENV": "false",
        "APP_MODE": "local",
        "AI_PROVIDER": "deterministic",
        "DATABASE_URL": url,
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("populated", [False, True])
def test_migration004_preserves_v1_rows_and_creates_empty_guarded_workflow_tables(
    tmp_path, populated
):
    from aegisgraph.services import execute_evaluations, seed_database

    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    migrate(url, "003_immutable_events")
    engine = make_engine(url)
    with Session(engine) as db:
        if populated:
            seed_database(db)
            execute_evaluations(db)
        previous = {
            table.name: list(db.execute(select(table)).mappings())
            for table in Base.metadata.sorted_tables
            if table.name in inspect(engine).get_table_names()
        }
    migrate(url, "head")
    with Session(engine) as db:
        assert {
            table.name: list(db.execute(select(table)).mappings())
            for table in Base.metadata.sorted_tables
            if table.name in previous
        } == previous
        for model in (m.RuleVersion, m.DetectionRegressionRun, m.RuleReview, m.RulesetState):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        revision = proposal(db)
        regression(db, revision)
        review(db, revision, None, "reject")
    for table in (
        "rule_versions",
        "detection_regression_runs",
        "rule_reviews",
        "events",
        "audit_log",
    ):
        # Existing source/audit guards and new immutable record guards survive upgrade.
        if table == "events" and not populated:
            continue
        for action in (f"UPDATE {table} SET id=id", f"DELETE FROM {table}"):
            with engine.begin() as connection:
                with pytest.raises(DatabaseError, match="append-only"):
                    connection.execute(text(action))
    engine.dispose()
