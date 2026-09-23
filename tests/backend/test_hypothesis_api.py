"""Hypothesis inspection stays scoped; only local human review persists."""

import pytest
import test_scenario_api as scenario_tests
from aegisgraph import config, main
from aegisgraph.analyst import OpenAIProvider
from aegisgraph.db import Base, get_db, make_engine
from aegisgraph.public_security import PublicBudget
from aegisgraph.services import seed_database
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

scenario_client = scenario_tests.scenario_client
scenario_database = scenario_tests.scenario_database
CASE = "INC-fe8fa4b9508c"
BASE = f"/api/incidents/{CASE}/hypotheses"


@pytest.fixture
def ledger_database(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_database(db)
    yield engine
    engine.dispose()


@pytest.fixture
def ledger_client(ledger_database):
    def override():
        with Session(ledger_database) as db:
            yield db

    main.app.dependency_overrides[get_db] = override
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()


def accept(client, ledger, kind="account_compromise"):
    row = next(item for item in ledger["items"] if item["kind"] == kind)
    return client.post(
        f"{BASE}/{kind}/review",
        json={
            "expected_version": row["review"]["version"],
            "context_digest": ledger["context_digest"],
            "review_status": "accepted",
            "related_finding_ids": [],
            "reason": "Reviewed the cited observations; identity attribution remains unverified.",
        },
    )


def test_ledger_reads_are_stable_and_do_not_write(scenario_client, scenario_database):
    client, mode = scenario_client
    before = scenario_tests.database_snapshot(scenario_database)
    response = client.get(BASE)
    assert response.status_code == 200
    ledger = response.json()
    assert ledger["read_only"] is (mode == "public_demo")
    assert len(ledger["items"]) == 4
    rows = {item["kind"]: item for item in ledger["items"]}
    assert rows["account_compromise"]["epistemic_status"] == "PARTIALLY_SUPPORTED"
    assert rows["suspicious_privilege_sequence"]["epistemic_status"] == "SUPPORTED"
    evidence_ids = {row["id"] for row in client.get(f"/api/incidents/{CASE}").json()["evidence"]}
    for item in ledger["items"]:
        assert (
            set(item["supporting_evidence_ids"] + item["contradicting_evidence_ids"])
            <= evidence_ids
        )
        assert item["review"]["version"] == 0
    assert client.get(BASE).content == response.content
    assert scenario_tests.database_snapshot(scenario_database) == before


def test_scenario_hypotheses_and_curated_analysis_use_completed_ephemeral_evidence(
    scenario_client, scenario_database, monkeypatch
):
    client, _mode = scenario_client
    monkeypatch.setenv("AI_PROVIDER", "openai")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Scenario inspection attempted a paid provider call")

    monkeypatch.setattr(OpenAIProvider, "generate", forbidden)
    before = scenario_tests.database_snapshot(scenario_database)
    for scenario in ("approved-admin", "bulk-automation", "mixed-context", "isolated-anomaly"):
        replay = client.get(f"/api/replays/{scenario}").json()
        scope = replay["final_state"]["investigation"]
        response = client.get(f"/api/scenarios/{scenario}/hypotheses")
        assert response.status_code == 200
        ledger = response.json()
        assert ledger["scope_id"] == scope["id"]
        assert ledger["scope_kind"] == scope["kind"]
        assert ledger["view"] == "completed_scenario"
        assert ledger["read_only"] is True
        ids = {row["id"] for row in scope["evidence"]}
        for row in ledger["items"]:
            assert set(row["supporting_evidence_ids"] + row["contradicting_evidence_ids"]) <= ids
        if scenario not in {"bulk-automation", "mixed-context"}:
            continue
        for question in ("summary", "malware"):
            answer = client.get(f"/api/scenarios/{scenario}/analysis/{question}")
            assert answer.status_code == 200
            result = answer.json()
            assert result["view"] == "completed_scenario"
            assert result["scope_id"] == scope["id"]
            assert result["analysis"]["provider"] == "deterministic"
            if question == "malware":
                assert result["analysis"]["status"] == "insufficient_evidence"
            for finding in result["analysis"]["findings"]:
                assert set(finding["evidence_ids"]) <= ids
    assert scenario_tests.database_snapshot(scenario_database) == before


def test_scenario_analyst_route_uses_existing_analysis_budget_category():
    assert (
        PublicBudget.category("GET", "/api/scenarios/bulk-automation/analysis/summary")
        == "analysis"
    )
    assert (
        PublicBudget.category("GET", "/api/scenarios/bulk-automation/analysis/malware")
        == "analysis"
    )
    assert PublicBudget.category("GET", "/api/scenarios/bulk-automation/hypotheses") == "read"


def test_gap_guidance_and_unknown_inputs_do_not_accept_arbitrary_questions(scenario_client):
    client, _ = scenario_client
    guide = client.get("/api/hypotheses/malware_execution/gaps")
    assert guide.status_code == 200
    assert "endpoint_forensics" in {row["category"] for row in guide.json()["missing_evidence"]}
    for path in (
        "/api/hypotheses/unknown/gaps",
        "/api/scenarios/unknown/hypotheses",
        "/api/scenarios/approved-admin/analysis/arbitrary",
        "/api/incidents/SCOPE-isolated-anomaly/hypotheses",
    ):
        assert client.get(path).status_code == 404
    for path in (
        "/api/hypotheses/malware_execution/gaps",
        "/api/scenarios/approved-admin/hypotheses",
        "/api/scenarios/approved-admin/analysis/summary",
    ):
        rejected = client.get(path, params={"question": "submitted-private-marker"})
        assert rejected.status_code == 422
        assert "submitted-private-marker" not in rejected.text


def test_human_review_does_not_promote_machine_status_and_invalidates_report(ledger_client):
    client = ledger_client
    ledger_response = client.get(BASE)
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    client.post(f"/api/incidents/{CASE}/report")
    assert client.post(f"/api/incidents/{CASE}/report/approve").status_code == 200
    response = accept(client, ledger)
    assert response.status_code == 200
    current = client.get(BASE).json()
    row = next(item for item in current["items"] if item["kind"] == "account_compromise")
    assert row["epistemic_status"] == "PARTIALLY_SUPPORTED"
    assert row["review"]["status"] == "accepted"
    assert row["review"]["version"] == 1
    assert client.get(f"/api/incidents/{CASE}/report").json()["status"] == "stale"
    report = client.post(f"/api/incidents/{CASE}/report").json()
    assert "Human-reviewed hypotheses" in report["content"]
    assert row["title"] in report["content"]
    assert "PARTIALLY_SUPPORTED" in report["content"]
    history = client.get(f"{BASE}/account_compromise/history")
    assert history.status_code == 200
    cited = row["supporting_evidence_ids"][0]
    changed = client.patch(f"/api/incidents/{CASE}/evidence/{cited}", json={"relevance": "benign"})
    assert changed.status_code == 200
    stale = client.get(BASE).json()
    assert (
        next(item for item in stale["items"] if item["kind"] == "account_compromise")["review"][
            "status"
        ]
        == "stale"
    )
    assert accept(client, current).status_code == 409
    refreshed_report = client.post(f"/api/incidents/{CASE}/report").json()
    assert row["title"] not in refreshed_report["content"]


def test_public_mode_never_exposes_saved_local_hypothesis_reviews(
    ledger_client, ledger_database, monkeypatch
):
    response = ledger_client.get(BASE)
    assert response.status_code == 200
    assert accept(ledger_client, response.json()).status_code == 200
    public = config.Settings(
        app_mode="public_demo",
        database_url="postgresql://demo:fixture-password@database.example/demo",
        allowed_origins=(scenario_tests.ORIGIN,),
        allowed_hosts=("testserver",),
    )
    monkeypatch.setattr(config, "settings", public)
    monkeypatch.setattr(main, "settings", public)
    before = scenario_tests.database_snapshot(ledger_database)
    public_ledger = ledger_client.get(BASE).json()
    assert all(row["review"]["version"] == 0 for row in public_ledger["items"])
    assert ledger_client.get(f"{BASE}/account_compromise/history").status_code == 404
    assert ledger_client.post(f"{BASE}/account_compromise/review", json={}).status_code == 403
    assert scenario_tests.database_snapshot(ledger_database) == before
