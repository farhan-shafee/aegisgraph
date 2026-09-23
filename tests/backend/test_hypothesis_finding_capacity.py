"""Existing finding creation cannot strand the bounded hypothesis/report workflow."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from aegisgraph import models as m
from aegisgraph import services as svc
from aegisgraph.db import Base, make_engine
from aegisgraph.hypothesis_workflow import get_ledger
from aegisgraph.schema import FindingCreate
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

CASE = "INC-fe8fa4b9508c"


def prepare(db):
    svc.seed_database(db)
    evidence_id = db.scalar(select(m.Evidence.id).where(m.Evidence.incident_id == CASE))
    for index in range(49):
        finding_id = f"FND-capacity-{index}"
        db.add(
            m.Finding(
                id=finding_id,
                incident_id=CASE,
                title="Synthetic observation",
                narrative="Human-authored fixture observation.",
                author="demo.analyst",
                approved=False,
            )
        )
        db.flush()
        db.add(m.FindingEvidence(finding_id=finding_id, evidence_id=evidence_id))
    db.commit()
    return FindingCreate(
        title="Another reviewed observation",
        narrative="Synthetic capacity boundary observation.",
        evidence_ids=[evidence_id],
    )


def snapshot(db):
    return {
        table.name: list(db.execute(select(table)).mappings())
        for table in Base.metadata.sorted_tables
    }


def test_fiftieth_finding_allowed_next_rejected_without_stranding_ledger_or_report():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        payload = prepare(db)
        result = svc.create_finding(db, CASE, payload)
        assert result["title"] == payload.title
        assert db.scalar(select(func.count()).select_from(m.Finding)) == 50
        before = snapshot(db)
        with pytest.raises(HTTPException) as rejected:
            svc.create_finding(db, CASE, payload)
        assert rejected.value.status_code == 409
        assert snapshot(db) == before
        db.rollback()
        assert len(get_ledger(db, CASE, public_demo=False)["items"]) == 4
        assert svc.generate_report(db, CASE)["status"] == "draft"
    engine.dispose()


def test_competing_finding_creates_cannot_exceed_per_case_capacity(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'finding-capacity.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        payload = prepare(db)
        before_audits = db.scalar(select(func.count()).select_from(m.Audit))
    ready = Barrier(2)

    def create(_):
        with Session(engine) as db:
            ready.wait(timeout=10)
            try:
                svc.create_finding(db, CASE, payload)
                return 201
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == [201, 409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(m.Finding)) == 50
        assert db.scalar(select(func.count()).select_from(m.Audit)) == before_audits + 1
        assert len(get_ledger(db, CASE, public_demo=False)["items"]) == 4
    engine.dispose()


def test_legacy_over_capacity_findings_are_preserved_and_report_remains_usable():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        payload = prepare(db)
        svc.create_finding(db, CASE, payload)
        # Simulate a pre-V2 record imported by an additive upgrade; current API
        # writes must not create this state, and migration must not delete it.
        db.add(
            m.Finding(
                id="FND-legacy-51",
                incident_id=CASE,
                title="Retained legacy observation",
                narrative="Historical human finding must remain available.",
                author="demo.analyst",
                approved=True,
            )
        )
        db.flush()
        db.add(m.FindingEvidence(finding_id="FND-legacy-51", evidence_id=payload.evidence_ids[0]))
        db.commit()
        before = snapshot(db)
        with pytest.raises(HTTPException) as rejected:
            get_ledger(db, CASE, public_demo=False)
        assert rejected.value.status_code == 409
        db.rollback()
        report = svc.generate_report(db, CASE)
        assert report["status"] == "draft"
        assert "Hypothesis review unavailable" in report["content"]
        assert "Retained legacy observation" in report["content"]
        assert "No current accepted hypothesis reviews" not in report["content"]
        after = snapshot(db)
        for table in Base.metadata.sorted_tables:
            primary_keys = [column.name for column in table.primary_key]
            retained = {tuple(row[key] for key in primary_keys): row for row in after[table.name]}
            assert all(
                retained.get(tuple(row[key] for key in primary_keys)) == row
                for row in before[table.name]
            )
        assert db.scalar(select(func.count()).select_from(m.Finding)) == 51
    engine.dispose()
