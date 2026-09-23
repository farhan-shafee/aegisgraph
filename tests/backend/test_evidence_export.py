"""Exports are bounded, consistently scoped read snapshots, never persisted writes."""

import copy
import importlib
import json
from datetime import UTC, datetime

import pytest
from aegisgraph import models as m
from aegisgraph.db import Base, make_engine
from aegisgraph.scenarios import scenario_events
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

INCIDENT = "INC-export"
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def exporter():
    try:
        return importlib.import_module("aegisgraph.evidence_export")
    except ModuleNotFoundError:
        pytest.fail("The scoped evidence export service is not implemented")


def populate(db):
    db.add(m.Incident(id=INCIDENT, title="Synthetic case", summary="Fixture", severity="medium"))
    db.flush()
    sources = scenario_events("auth-pressure")
    for index, source in enumerate(sources):
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
        db.add(m.Evidence(id=f"EVD-export-{index}", incident_id=INCIDENT, event_id=source.event_id))
    db.add(
        m.Alert(
            id="ALT-export",
            rule_id="AUTH-002",
            rule_name="Unfamiliar authentication",
            severity="medium",
            description="Synthetic signal",
            timestamp=sources[-1].timestamp,
            user_id=sources[-1].actor.user_id,
        )
    )
    db.flush()
    db.add(m.IncidentAlert(incident_id=INCIDENT, alert_id="ALT-export"))
    db.add(m.AlertEvent(alert_id="ALT-export", event_id=sources[-1].event_id))
    db.add(m.Note(id="NOTE-export", incident_id=INCIDENT, text="Human note", author="analyst"))
    db.add(
        m.Finding(
            id="FND-export",
            incident_id=INCIDENT,
            title="Observed activity",
            narrative="Human finding",
            author="analyst",
        )
    )
    db.flush()
    db.add(m.FindingEvidence(finding_id="FND-export", evidence_id="EVD-export-0"))
    db.add(
        m.Audit(
            id="AUD-export",
            incident_id=INCIDENT,
            actor="analyst",
            actor_type="human",
            action="note_created",
            object_id="NOTE-export",
        )
    )
    db.commit()


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'export.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        populate(session)
        yield session
    engine.dispose()


def tables(db):
    with Session(db.get_bind()) as inspection:
        return {
            table.name: list(inspection.execute(select(table)).mappings())
            for table in Base.metadata.sorted_tables
        }


def snapshot(db, monkeypatch, public=False):
    module = exporter()
    monkeypatch.setattr(module, "build_bundle", lambda value, **kwargs: copy.deepcopy(value))
    return module.export_incident(db, INCIDENT, public_demo=public, generated_at=NOW)


def test_scoped_export_reads_all_supported_collections_without_database_changes(db, monkeypatch):
    before = tables(db)
    result = snapshot(db, monkeypatch)
    assert result["incident"]["id"] == INCIDENT
    assert result["scenario_id"] is None
    assert len(result["evidence"]) == 10
    assert len(result["alerts"]) == len(result["findings"]) == len(result["notes"]) == 1
    assert len(result["hypotheses"]["items"]) == 4
    assert result["audit"][0]["incident_id"] == INCIDENT
    assert result["entities"]["nodes"] and result["entities"]["edges"]
    assert tables(db) == before


def test_public_snapshot_omits_human_artifacts_without_querying_their_tables(db, monkeypatch):
    case = db.get(m.Incident, INCIDENT)
    case.owner = "PRIVATE-OWNER"
    db.get(m.Evidence, "EVD-export-0").note = "PRIVATE-EVIDENCE-NOTE"
    db.commit()
    before = tables(db)
    queries = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        queries.append(statement.lower())

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        result = snapshot(db, monkeypatch, public=True)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)
    assert result["findings"] == result["notes"] == result["audit"] == []
    assert result["incident"]["owner"] is None
    assert all(item["note"] == "" for item in result["evidence"])
    serialized = json.dumps(result)
    assert "PRIVATE-" not in serialized and "Human note" not in serialized
    assert not any(
        any(
            f"from {table}" in query or f"join {table}" in query
            for table in (
                "findings",
                "notes",
                "audit_log",
                "hypothesis_states",
                "hypothesis_revisions",
            )
        )
        for query in queries
    )
    assert not any(query.lstrip().startswith(("update", "insert", "delete")) for query in queries)
    assert tables(db) == before


def test_unknown_case_is_safe_404_and_has_no_side_effects(db):
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        exporter().export_incident(db, "INC-missing", public_demo=False, generated_at=NOW)
    assert caught.value.status_code == 404
    assert tables(db) == before


def test_export_uses_committed_data_without_flushing_callers_pending_changes(db, monkeypatch):
    db.add(m.Note(id="NOTE-pending", incident_id=INCIDENT, text="UNCOMMITTED", author="analyst"))
    result = snapshot(db, monkeypatch)
    assert [row["id"] for row in result["notes"]] == ["NOTE-export"]
    assert any(row.id == "NOTE-pending" for row in db.new)
    db.rollback()


@pytest.mark.parametrize("kind", ["finding", "alert"])
def test_cross_case_references_are_rejected_without_side_effects(db, monkeypatch, kind):
    source = scenario_events("bulk-automation")[0]
    db.add(m.Incident(id="INC-other", title="Other", summary="Other", severity="low"))
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
    db.add(m.Evidence(id="EVD-foreign", incident_id="INC-other", event_id=source.event_id))
    db.flush()
    if kind == "finding":
        db.add(m.FindingEvidence(finding_id="FND-export", evidence_id="EVD-foreign"))
    else:
        db.add(m.AlertEvent(alert_id="ALT-export", event_id=source.event_id))
    db.commit()
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        snapshot(db, monkeypatch)
    assert caught.value.status_code == 409
    assert tables(db) == before


@pytest.mark.parametrize("collection,maximum", [("findings", 50), ("notes", 100), ("audit", 1000)])
def test_collection_limits_reject_instead_of_truncating(db, monkeypatch, collection, maximum):
    for index in range(maximum):
        if collection == "findings":
            row = m.Finding(
                id=f"FND-limit-{index}",
                incident_id=INCIDENT,
                title="Observed",
                narrative="Fixture",
                author="analyst",
            )
        elif collection == "notes":
            row = m.Note(
                id=f"NOTE-limit-{index}", incident_id=INCIDENT, text="Fixture", author="analyst"
            )
        else:
            row = m.Audit(
                id=f"AUD-limit-{index}",
                incident_id=INCIDENT,
                actor="analyst",
                actor_type="human",
                action="fixture",
                object_id=INCIDENT,
            )
        db.add(row)
    db.commit()
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        snapshot(db, monkeypatch)
    assert caught.value.status_code == 409
    assert tables(db) == before


def test_oversized_free_text_is_rejected_before_loading_payload(db, monkeypatch):
    db.get(m.Note, "NOTE-export").text = "x" * 70000
    db.commit()
    loaded = []

    def track(_session, instance):
        if isinstance(instance, m.Note):
            loaded.append(instance.id)

    event.listen(Session, "loaded_as_persistent", track)
    try:
        with pytest.raises(HTTPException) as caught:
            snapshot(db, monkeypatch)
    finally:
        event.remove(Session, "loaded_as_persistent", track)
    assert caught.value.status_code == 409 and not loaded


@pytest.mark.parametrize("collection", ["evidence", "alerts"])
def test_evidence_and_alert_bounds_fail_closed(db, monkeypatch, collection):
    source = scenario_events("bulk-automation")[0]
    if collection == "evidence":
        for index in range(71):
            identifier = f"EVT-extra-{index}"
            payload = source.model_dump(mode="json")
            payload["event_id"] = identifier
            db.add(
                m.SecurityEvent(
                    id=identifier,
                    timestamp=source.timestamp,
                    source=source.source,
                    event_type=source.event_type,
                    user_id=source.actor.user_id,
                    session_id=source.session.session_id,
                    payload=payload,
                )
            )
            db.flush()
            db.add(m.Evidence(id=f"EVD-extra-{index}", incident_id=INCIDENT, event_id=identifier))
    else:
        for index in range(80):
            identifier = f"ALT-extra-{index}"
            db.add(
                m.Alert(
                    id=identifier,
                    rule_id="AUTH-002",
                    rule_name="Synthetic",
                    severity="medium",
                    description="Fixture",
                    timestamp=source.timestamp,
                    user_id=source.actor.user_id,
                )
            )
            db.flush()
            db.add(m.IncidentAlert(incident_id=INCIDENT, alert_id=identifier))
    db.commit()
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        snapshot(db, monkeypatch)
    assert caught.value.status_code == 409
    assert tables(db) == before


def test_in_memory_shared_connection_cannot_rollback_callers_flushed_transaction(monkeypatch):
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        populate(db)
        pending = m.Note(
            id="NOTE-pending", incident_id=INCIDENT, text="UNCOMMITTED", author="analyst"
        )
        db.add(pending)
        db.flush()
        with pytest.raises(HTTPException) as caught:
            snapshot(db, monkeypatch)
        assert caught.value.status_code == 409
        assert db.get(m.Note, "NOTE-pending").text == "UNCOMMITTED"
        db.commit()
    with Session(engine) as verification:
        assert verification.get(m.Note, "NOTE-pending") is not None
    engine.dispose()


def test_fresh_reader_session_cannot_rollback_another_shared_pool_session(monkeypatch):
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as writer, Session(engine) as reader:
        populate(writer)
        writer.add(
            m.Note(id="NOTE-pending", incident_id=INCIDENT, text="UNCOMMITTED", author="analyst")
        )
        writer.flush()
        with pytest.raises(HTTPException) as caught:
            snapshot(reader, monkeypatch)
        assert caught.value.status_code == 409
        writer.commit()
    with Session(engine) as verification:
        assert verification.get(m.Note, "NOTE-pending") is not None
    engine.dispose()


def test_export_observes_one_snapshot_when_writer_commits_between_reads(db, monkeypatch):
    engine = db.get_bind()
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    committed = False

    def concurrent_write(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal committed
        if not committed and "FROM notes" in statement and "length(" in statement:
            committed = True
            with Session(engine) as writer:
                writer.get(m.Incident, INCIDENT).summary = "Changed concurrently"
                writer.get(m.Note, "NOTE-export").text = "Changed concurrently"
                writer.commit()

    event.listen(engine, "before_cursor_execute", concurrent_write)
    try:
        result = snapshot(db, monkeypatch)
    finally:
        event.remove(engine, "before_cursor_execute", concurrent_write)
    assert committed
    assert result["incident"]["summary"] == "Fixture"
    assert result["notes"][0]["text"] == "Human note"
    with Session(engine) as verification:
        assert (
            verification.scalar(text("SELECT summary FROM incidents WHERE id='INC-export'"))
            == "Changed concurrently"
        )
        assert verification.get(m.Note, "NOTE-export").text == "Changed concurrently"


@pytest.mark.parametrize("collection", ["notes", "audit", "findings"])
def test_aggregate_payload_capacity_is_checked_before_orm_rows_load(db, monkeypatch, collection):
    for index in range(10):
        payload = "x" * 30000 if collection == "audit" else "😀" * 8000
        if collection == "notes":
            row = m.Note(
                id=f"NOTE-size-{index}", incident_id=INCIDENT, text=payload, author="analyst"
            )
            model = m.Note
        elif collection == "findings":
            row = m.Finding(
                id=f"FND-size-{index}",
                incident_id=INCIDENT,
                title="Observed",
                narrative=payload,
                author="analyst",
            )
            model = m.Finding
        else:
            row = m.Audit(
                id=f"AUD-size-{index}",
                incident_id=INCIDENT,
                actor="analyst",
                actor_type="human",
                action="fixture",
                object_id=INCIDENT,
                after={"note": payload},
            )
            model = m.Audit
        db.add(row)
    db.commit()
    loaded = []

    def track(_session, instance):
        if isinstance(instance, model):
            loaded.append(instance.id)

    event.listen(Session, "loaded_as_persistent", track)
    try:
        with pytest.raises(HTTPException) as caught:
            snapshot(db, monkeypatch)
    finally:
        event.remove(Session, "loaded_as_persistent", track)
    assert caught.value.status_code == 409 and not loaded


@pytest.mark.parametrize("public", [False, True])
def test_actual_builder_returns_verifiable_deterministic_bundle(db, public):
    from aegisgraph.evidence_bundle import verify_bundle

    before = tables(db)
    first = exporter().export_incident(db, INCIDENT, public_demo=public, generated_at=NOW)
    second = exporter().export_incident(db, INCIDENT, public_demo=public, generated_at=NOW)
    assert first == second
    assert verify_bundle(first)["status"] == "VALID"
    assert first["manifest"]["projection"] == ("public_synthetic" if public else "local_review")
    assert tables(db) == before


@pytest.mark.parametrize("reference", ["evidence_ids", "related_finding_ids", "event_ids"])
def test_audit_nested_structured_foreign_references_reject_whole_export(db, reference):
    db.add(
        m.Audit(
            id="AUD-foreign-reference",
            incident_id=INCIDENT,
            actor="analyst",
            actor_type="human",
            action="finding_created",
            object_id="FND-export",
            after={"detail": {reference: ["foreign-reference"]}},
        )
    )
    db.commit()
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        exporter().export_incident(db, INCIDENT, public_demo=False, generated_at=NOW)
    assert caught.value.status_code == 409
    assert "foreign-reference" not in caught.value.detail
    assert tables(db) == before


def test_foreign_hypothesis_review_reference_rejected_locally_and_omitted_publicly(db):
    from aegisgraph.hypothesis_workflow import get_ledger

    current = get_ledger(db, INCIDENT, public_demo=False)
    hypothesis = current["items"][0]
    db.add(
        m.HypothesisState(
            id=hypothesis["id"], incident_id=INCIDENT, kind=hypothesis["kind"], current_version=1
        )
    )
    db.flush()
    db.add(
        m.HypothesisRevision(
            id="HREV-foreign",
            state_id=hypothesis["id"],
            version=1,
            snapshot=hypothesis,
            context_digest=current["context_digest"],
            review_status="accepted",
            related_finding_ids=["FND-foreign"],
            reason="PRIVATE-REVIEW",
            actor_label="PRIVATE-ACTOR",
        )
    )
    db.commit()
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        exporter().export_incident(db, INCIDENT, public_demo=False, generated_at=NOW)
    assert caught.value.status_code == 409
    public = exporter().export_incident(db, INCIDENT, public_demo=True, generated_at=NOW)
    assert "PRIVATE-" not in json.dumps(public) and "FND-foreign" not in json.dumps(public)
    assert tables(db) == before


def test_real_human_hypothesis_review_history_is_exportable(db):
    from aegisgraph.evidence_bundle import verify_bundle
    from aegisgraph.hypothesis_workflow import (
        ReviewHypothesisRequest,
        get_ledger,
        review_hypothesis,
    )

    kind = "account_compromise"
    for version in range(2):
        current = get_ledger(db, INCIDENT, public_demo=False)
        review_hypothesis(
            db,
            INCIDENT,
            kind,
            ReviewHypothesisRequest(
                expected_version=version,
                context_digest=current["context_digest"],
                review_status="accepted" if version == 0 else "open",
                related_finding_ids=["FND-export"],
                reason=f"Synthetic review {version + 1}",
            ),
            actor_label="demo.analyst",
            public_demo=False,
        )
    before = tables(db)
    bundle = exporter().export_incident(db, INCIDENT, public_demo=False, generated_at=NOW)
    files = {row["path"]: row["content"] for row in bundle["files"]}
    reviews = [
        row for row in json.loads(files["audit.json"]) if row["action"] == "hypothesis_reviewed"
    ]
    assert len(reviews) == 2 and all(row["object_id"].startswith("HPR-") for row in reviews)
    ledger = json.loads(files["hypotheses.json"])
    assert next(row for row in ledger["items"] if row["kind"] == kind)["review"]["version"] == 2
    assert verify_bundle(bundle)["status"] == "VALID"
    assert tables(db) == before


def test_hypothesis_audit_revision_must_belong_to_exported_incident(db):
    from aegisgraph.hypothesis_workflow import get_ledger

    current = get_ledger(db, INCIDENT, public_demo=False)
    db.add(m.Incident(id="INC-other", title="Other", summary="Other", severity="low"))
    db.flush()
    db.add(
        m.HypothesisState(
            id="HYP-other", incident_id="INC-other", kind="account_compromise", current_version=1
        )
    )
    db.flush()
    db.add(
        m.HypothesisRevision(
            id="HPR-foreign",
            state_id="HYP-other",
            version=1,
            snapshot={},
            context_digest="a" * 64,
            review_status="open",
            related_finding_ids=[],
            reason="Other",
            actor_label="analyst",
        )
    )
    db.add(
        m.Audit(
            id="AUD-foreign-revision",
            incident_id=INCIDENT,
            actor="analyst",
            actor_type="human",
            action="hypothesis_reviewed",
            object_id="HPR-foreign",
            after={"hypothesis_id": current["items"][0]["id"]},
        )
    )
    db.commit()
    before = tables(db)
    with pytest.raises(HTTPException) as caught:
        exporter().export_incident(db, INCIDENT, public_demo=False, generated_at=NOW)
    assert caught.value.status_code == 409
    assert tables(db) == before
