"""Human reviews are scoped, versioned records separate from derived evidence claims."""

import copy
import hashlib
import importlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, local

import pytest
from aegisgraph import models as m
from aegisgraph.config import ROOT
from aegisgraph.db import Base, make_engine
from aegisgraph.scenarios import scenario_events
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

INCIDENT = "INC-hypothesis"
KIND = "account_compromise"


def evidence_id(event_id, incident=INCIDENT):
    return "EVD-" + hashlib.sha256(f"{incident}:{event_id}".encode()).hexdigest()[:16]


FIRST_EVIDENCE = evidence_id(scenario_events("auth-pressure")[0].event_id)


def workflow():
    try:
        return importlib.import_module("aegisgraph.hypothesis_workflow")
    except ModuleNotFoundError:
        pytest.fail("The hypothesis review workflow has not been implemented")


def populate(db):
    db.add(
        m.Incident(
            id=INCIDENT, title="Synthetic investigation", summary="Fixture", severity="medium"
        )
    )
    db.flush()
    for source in scenario_events("auth-pressure"):
        db.add(
            m.SecurityEvent(
                id=source.event_id,
                timestamp=source.timestamp,
                source=source.source,
                event_type=source.event_type,
                user_id=source.actor.user_id,
                session_id=source.session.session_id,
                payload=source.model_dump(mode="json"),
            )
        )
        db.flush()
        db.add(
            m.Evidence(
                id=evidence_id(source.event_id), incident_id=INCIDENT, event_id=source.event_id
            )
        )
    db.commit()


@pytest.fixture
def db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        populate(session)
        yield session
    engine.dispose()


def rows(db):
    return {
        table.name: list(db.execute(select(table)).mappings())
        for table in Base.metadata.sorted_tables
    }


def ledger(db, public=False):
    return workflow().get_ledger(db, INCIDENT, public_demo=public)


def payload(db, **changes):
    current = ledger(db)
    item = next(item for item in current["items"] if item["kind"] == KIND)
    return workflow().ReviewHypothesisRequest(
        **{
            "expected_version": item["review"]["version"],
            "context_digest": current["context_digest"],
            "review_status": "accepted",
            "related_finding_ids": [],
            "reason": "Reviewed the scoped observations and remaining gaps.",
            **changes,
        }
    )


def review(db, request=None):
    return workflow().review_hypothesis(
        db, INCIDENT, KIND, request or payload(db), actor_label="demo.analyst", public_demo=False
    )


def test_reads_derive_four_candidates_without_creating_persistent_rows(db):
    before = rows(db)
    result = ledger(db)
    assert result["scope_id"] == INCIDENT and result["read_only"] is False
    assert len(result["items"]) == 4 and len(result["context_digest"]) == 64
    assert all(
        item["review"]["version"] == 0 and item["review"]["status"] == "open"
        for item in result["items"]
    )
    assert workflow().get_hypothesis_history(db, INCIDENT, KIND, public_demo=False)["history"] == []
    assert rows(db) == before


def test_review_preserves_machine_status_and_invalidates_report_with_scoped_audit(db):
    before = ledger(db)
    db.add(
        m.Report(
            id="RPT-hyp",
            incident_id=INCIDENT,
            title="Reviewed",
            content="Synthetic",
            status="approved",
            approved_by="demo.analyst",
            approved_at=m.utcnow(),
        )
    )
    db.commit()
    result = review(db)
    item = next(item for item in result["items"] if item["kind"] == KIND)
    original = next(item for item in before["items"] if item["kind"] == KIND)
    assert item["epistemic_status"] == original["epistemic_status"]
    assert item["review"]["status"] == "accepted" and item["review"]["version"] == 1
    assert item["review"]["actor_label"] == "demo.analyst"
    assert db.get(m.Report, "RPT-hyp").status == "stale"
    assert db.get(m.Report, "RPT-hyp").approved_at is None
    record = db.scalar(select(m.HypothesisRevision))
    assert record.snapshot["epistemic_status"] == original["epistemic_status"]
    audit = db.scalar(select(m.Audit).where(m.Audit.action == "hypothesis_reviewed"))
    assert audit.incident_id == INCIDENT and audit.actor_type == "human"
    assert audit.after["context_digest"] == result["context_digest"]
    assert audit.after["reason"] == item["review"]["reason"]
    assert (
        workflow().get_hypothesis_history(db, INCIDENT, KIND, public_demo=False)["history"][0][
            "version"
        ]
        == 1
    )


def add_finding(db, *, incident=INCIDENT, finding_id="FND-hyp", evidence_id=FIRST_EVIDENCE):
    if incident != INCIDENT:
        db.add(m.Incident(id=incident, title="Other case", summary="Fixture", severity="low"))
        db.flush()
    db.add(
        m.Finding(
            id=finding_id,
            incident_id=incident,
            title="Observed auth",
            narrative="Observed synthetic activity",
            author="demo.analyst",
            approved=True,
        )
    )
    db.flush()
    if evidence_id:
        db.add(m.FindingEvidence(finding_id=finding_id, evidence_id=evidence_id))
    db.commit()


def test_linked_findings_are_validated_and_versioned_without_promoting_claims(db):
    add_finding(db)
    review(db, payload(db, related_finding_ids=["FND-hyp"]))
    item = next(item for item in ledger(db)["items"] if item["kind"] == KIND)
    assert item["review"]["related_finding_ids"] == ["FND-hyp"]
    assert db.scalar(select(m.HypothesisRevision)).related_finding_ids == ["FND-hyp"]
    review(db, payload(db, review_status="rejected"))
    history = workflow().get_hypothesis_history(db, INCIDENT, KIND, public_demo=False)["history"]
    assert [item["version"] for item in history] == [2, 1]
    assert [item["review_status"] for item in history] == ["rejected", "accepted"]


def test_cross_case_or_unknown_related_findings_are_rejected(db):
    add_finding(db, incident="INC-other", finding_id="FND-other", evidence_id=None)
    for reference in ("FND-other", "FND-missing"):
        before = rows(db)
        with pytest.raises(HTTPException) as result:
            review(db, payload(db, related_finding_ids=[reference]))
        assert result.value.status_code == 422
        assert rows(db) == before


def test_cross_case_citations_in_current_finding_fail_closed(db):
    add_finding(db, incident="INC-other", finding_id="FND-other", evidence_id=None)
    source = db.get(m.Evidence, FIRST_EVIDENCE)
    db.add(m.Evidence(id="EVD-other", incident_id="INC-other", event_id=source.event_id))
    db.commit()
    add_finding(db, evidence_id="EVD-other")
    with pytest.raises(HTTPException) as result:
        ledger(db)
    assert result.value.status_code == 409


@pytest.mark.parametrize("field", ["title", "narrative", "approved", "citations"])
def test_changed_existing_finding_invalidates_review_even_when_not_linked(db, field):
    add_finding(db)
    review(db)
    previous = payload(db)
    finding = db.get(m.Finding, "FND-hyp")
    if field == "citations":
        second = evidence_id(scenario_events("auth-pressure")[1].event_id)
        db.add(m.FindingEvidence(finding_id=finding.id, evidence_id=second))
    elif field == "approved":
        finding.approved = False
    else:
        setattr(finding, field, "Changed human finding context")
    db.commit()
    current = ledger(db)
    assert (
        next(item for item in current["items"] if item["kind"] == KIND)["review"]["status"]
        == "stale"
    )
    with pytest.raises(HTTPException) as result:
        review(db, previous)
    assert result.value.status_code == 409


@pytest.mark.parametrize("change", ["annotation", "finding", "derivation"])
def test_context_changes_make_old_reviews_stale_and_reject_stale_submission(
    db, monkeypatch, change
):
    review(db)
    previous = payload(db)
    if change == "annotation":
        db.get(m.Evidence, FIRST_EVIDENCE).note = "New human observation"
        db.commit()
    elif change == "finding":
        add_finding(db)
    else:
        original = workflow().build_ledger

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            result["items"][0]["provenance"]["derivation_version"] = "future-version"
            return result

        monkeypatch.setattr(workflow(), "build_ledger", changed)
    current = ledger(db)
    assert (
        next(item for item in current["items"] if item["kind"] == KIND)["review"]["status"]
        == "stale"
    )
    before = rows(db)
    with pytest.raises(HTTPException) as result:
        review(db, previous)
    assert result.value.status_code == 409 and rows(db) == before


def test_stale_version_is_rejected_even_when_context_is_unchanged(db):
    previous = payload(db)
    review(db, previous)
    with pytest.raises(HTTPException) as result:
        review(db, previous)
    assert result.value.status_code == 409
    assert db.scalar(select(func.count()).select_from(m.HypothesisRevision)) == 1


def test_public_reads_never_query_local_findings_or_review_state(db):
    add_finding(db)
    review(db)
    before = rows(db)

    def deny_workflow_reads(_connection, _cursor, statement, _parameters, _context, _many):
        assert not any(
            name in statement.lower()
            for name in (
                "hypothesis_states",
                "hypothesis_revisions",
                "findings",
                "finding_evidence",
            )
        )

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", deny_workflow_reads)
    try:
        result = ledger(db, public=True)
        assert result["read_only"] and all(
            item["review"]["version"] == 0 for item in result["items"]
        )
    finally:
        event.remove(engine, "before_cursor_execute", deny_workflow_reads)
    assert rows(db) == before


def test_public_history_and_writes_reject_before_touching_database():
    class ForbiddenDatabase:
        def __getattr__(self, name):
            pytest.fail("Public history and writes must reject before inspecting storage")

    with pytest.raises(HTTPException) as result:
        workflow().get_hypothesis_history(ForbiddenDatabase(), INCIDENT, KIND, public_demo=True)
    assert result.value.status_code == 404
    with pytest.raises(HTTPException) as result:
        workflow().review_hypothesis(
            ForbiddenDatabase(), INCIDENT, KIND, {}, actor_label="demo.analyst", public_demo=True
        )
    assert result.value.status_code == 403


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_version": True},
        {"expected_version": "0"},
        {"review_status": "supported"},
        {"epistemic_status": "supported"},
        {"reason": "  "},
        {"related_finding_ids": ["FND-a", "FND-a"]},
        {"related_finding_ids": ["../other"]},
        {"context_digest": "invalid"},
    ],
)
def test_request_rejects_untyped_or_machine_state_overrides(db, changes):
    with pytest.raises(ValidationError):
        payload(db, **changes)


def test_constructed_request_is_revalidated_and_unknown_scope_or_kind_is_404(db):
    request = payload(db).model_copy(update={"expected_version": True})
    with pytest.raises(HTTPException) as result:
        review(db, request)
    assert result.value.status_code == 422
    for scope, kind in (("SCOPE-demo", KIND), (INCIDENT, "invented")):
        with pytest.raises(HTTPException) as result:
            workflow().review_hypothesis(
                db, scope, kind, payload(db), actor_label="demo.analyst", public_demo=False
            )
        assert result.value.status_code == 404


def test_twenty_revision_capacity_is_enforced_without_partial_audit(db):
    for _ in range(20):
        review(db)
    before = rows(db)
    with pytest.raises(HTTPException) as result:
        review(db)
    assert result.value.status_code == 409 and rows(db) == before


@pytest.mark.parametrize("resource", ["evidence", "findings"])
def test_context_limits_fail_before_truncating_visible_state(db, resource):
    if resource == "findings":
        db.add_all(
            m.Finding(
                id=f"FND-limit-{index}",
                incident_id=INCIDENT,
                title="Synthetic",
                narrative="Bounded test",
                author="demo.analyst",
            )
            for index in range(51)
        )
    else:
        template = db.scalar(select(m.SecurityEvent))
        for index in range(71):
            event_id = f"EVT-limit-{index}"
            data = copy.deepcopy(template.payload)
            data["event_id"] = event_id
            db.add(
                m.SecurityEvent(
                    id=event_id,
                    timestamp=template.timestamp,
                    source=template.source,
                    event_type=template.event_type,
                    user_id=template.user_id,
                    session_id=template.session_id,
                    payload=data,
                )
            )
            db.flush()
            db.add(m.Evidence(id=evidence_id(event_id), incident_id=INCIDENT, event_id=event_id))
    db.commit()
    with pytest.raises(HTTPException) as result:
        ledger(db)
    assert result.value.status_code == 409


@pytest.mark.parametrize("action", ["update", "delete"])
def test_revision_records_are_immutable_at_orm_boundary(db, action):
    review(db)
    record = db.scalar(select(m.HypothesisRevision))
    if action == "update":
        record.reason = "Changed history"
    else:
        db.delete(record)
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()


def test_concurrent_reviews_accept_only_one_expected_version(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'concurrent-hypotheses.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        populate(db)
        request = payload(db)
    ready = Barrier(2)

    def submit(_):
        with Session(engine) as db:
            ready.wait(timeout=10)
            try:
                review(db, request)
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, range(2))) == [200, 409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(m.HypothesisRevision)) == 1
    engine.dispose()


def test_evidence_writer_holds_shared_case_lock_until_stale_review_is_rejected(
    tmp_path, monkeypatch
):
    from aegisgraph import services as svc

    original_lock = svc.lock_incident
    engine = make_engine(f"sqlite:///{tmp_path / 'evidence-review-race.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        populate(db)
        request = payload(db)
    writer_locked, review_attempted = Event(), Event()
    role = local()

    def observed_lock(db, incident_id):
        result = original_lock(db, incident_id)
        if getattr(role, "name", None) == "writer":
            writer_locked.set()
            assert review_attempted.wait(timeout=10)
        return result

    def observe_sql(_connection, _cursor, statement, _parameters, _context, _many):
        if getattr(role, "name", None) == "review" and statement.lstrip().upper().startswith(
            "UPDATE INCIDENTS"
        ):
            review_attempted.set()

    monkeypatch.setattr(svc, "lock_incident", observed_lock)
    event.listen(engine, "before_cursor_execute", observe_sql)

    def write_evidence():
        role.name = "writer"
        with Session(engine) as db:
            svc.patch_evidence(
                db, INCIDENT, FIRST_EVIDENCE, {"note": "Concurrent human context change"}
            )

    def submit_review():
        role.name = "review"
        assert writer_locked.wait(timeout=10)
        with Session(engine) as db:
            with pytest.raises(HTTPException) as result:
                review(db, request)
            assert result.value.status_code == 409

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(write_evidence)
            reviewer = pool.submit(submit_review)
            writer.result(timeout=20)
            reviewer.result(timeout=20)
        with Session(engine) as db:
            assert db.get(m.Evidence, FIRST_EVIDENCE).note == "Concurrent human context change"
            assert db.scalar(select(func.count()).select_from(m.HypothesisRevision)) == 0
    finally:
        event.remove(engine, "before_cursor_execute", observe_sql)
        engine.dispose()


def test_public_readiness_rejects_hypothesis_saved_work(db):
    from aegisgraph import deployment
    from aegisgraph.services import execute_evaluations, seed_database

    # Use a separate clean seed rather than the small workflow unit fixture.
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
        execute_evaluations(session)
        assert deployment.dataset_status(session)["ready"]
        current = workflow().get_ledger(session, deployment.FLAGSHIP_ID, public_demo=False)
        workflow().review_hypothesis(
            session,
            deployment.FLAGSHIP_ID,
            KIND,
            workflow().ReviewHypothesisRequest(
                expected_version=0,
                context_digest=current["context_digest"],
                review_status="open",
                reason="Initial local human review.",
            ),
            actor_label="demo.analyst",
            public_demo=False,
        )
        assert not deployment.dataset_status(session)["ready"]
    engine.dispose()


@pytest.mark.parametrize("populated", [False, True])
def test_migration005_preserves_previous_rows_and_guards_immutable_revisions(tmp_path, populated):
    url = f"sqlite:///{tmp_path / 'hypothesis-upgrade.db'}"
    environment = {
        **os.environ,
        "AEGISGRAPH_LOAD_ENV": "false",
        "APP_MODE": "local",
        "AI_PROVIDER": "deterministic",
        "DATABASE_URL": url,
    }

    def migrate(revision):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    migrate("004_rule_workflow")
    engine = make_engine(url)
    with Session(engine) as db:
        if populated:
            populate(db)
        before = {
            table.name: list(db.execute(select(table)).mappings())
            for table in Base.metadata.sorted_tables
            if table.name in inspect(engine).get_table_names()
        }
    migrate("head")
    with Session(engine) as db:
        assert {
            table.name: list(db.execute(select(table)).mappings())
            for table in Base.metadata.sorted_tables
            if table.name in before
        } == before
        assert db.scalar(select(func.count()).select_from(m.HypothesisState)) == 0
        assert db.scalar(select(func.count()).select_from(m.HypothesisRevision)) == 0
        if not populated:
            populate(db)
        review(db)
    for command in (
        "UPDATE hypothesis_revisions SET id=id",
        "DELETE FROM hypothesis_revisions",
        "UPDATE events SET id=id",
        "DELETE FROM audit_log",
    ):
        with engine.begin() as connection, pytest.raises(DatabaseError, match="append-only"):
            connection.execute(text(command))
    engine.dispose()
