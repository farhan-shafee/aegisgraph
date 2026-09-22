"""The rule workbench exposes typed local review and read-only public examples."""

import pytest
import test_scenario_api as scenario_tests
from aegisgraph import config, main
from aegisgraph.db import Base, get_db, make_engine
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

scenario_client = scenario_tests.scenario_client
scenario_database = scenario_tests.scenario_database


@pytest.fixture
def rule_database(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'rules.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def rule_client(rule_database):

    def override():
        with Session(rule_database) as db:
            yield db

    main.app.dependency_overrides[get_db] = override
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()


def test_public_reads_ignore_preexisting_local_approved_rules(
    rule_client, rule_database, monkeypatch
):
    revision = proposal(rule_client, 1500).json()
    run = rule_client.post(f"/api/detection-versions/{revision['id']}/regressions").json()
    review = rule_client.post(
        f"/api/detection-versions/{revision['id']}/review",
        json={
            "decision": "approve",
            "regression_id": run["id"],
            "reason": "Reviewed fixture changes.",
        },
    )
    assert review.status_code == 200
    public = config.Settings(
        app_mode="public_demo",
        database_url="postgresql://demo:fixture-password@database.example/demo",
        allowed_origins=(scenario_tests.ORIGIN,),
        allowed_hosts=("testserver",),
    )
    monkeypatch.setattr(config, "settings", public)
    monkeypatch.setattr(main, "settings", public)
    before = scenario_tests.database_snapshot(rule_database)
    response = rule_client.get("/api/detections/APP-002/workbench")
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert response.json()["revisions"] == []
    assert response.json()["rule"]["threshold"] == 1000
    assert rule_client.get(f"/api/detection-versions/{revision['id']}").status_code == 404
    replay = rule_client.get("/api/replays/bulk-automation")
    assert replay.status_code == 200
    assert len(replay.json()["final_state"]["alerts"]) == 1
    assert scenario_tests.database_snapshot(rule_database) == before


def proposal(client, threshold):
    response = client.get("/api/detections/APP-002/workbench")
    assert response.status_code == 200
    base = response.json()
    return client.post(
        "/api/detections/APP-002/versions",
        json={
            "parameters": {"threshold": threshold},
            "base_ruleset_digest": base["ruleset_digest"],
            "base_generation": base["generation"],
            "base_version": base["version"],
            "reason": "Compare scheduled reconciliation with required access signals.",
        },
    )


def test_local_tuning_runs_real_regression_and_approval_changes_subsequent_replay(rule_client):
    client = rule_client
    before = client.get("/api/replays/bulk-automation").json()
    assert len(before["final_state"]["alerts"]) == 1
    created = proposal(client, 1500)
    assert created.status_code == 201
    revision = created.json()
    assert revision["version"] == 2 and revision["status"] == "proposed"
    run = client.post(f"/api/detection-versions/{revision['id']}/regressions")
    assert run.status_code == 201
    result = run.json()
    assert result["result"]["gate"]["decision"] == "PASS"
    review = client.post(
        f"/api/detection-versions/{revision['id']}/review",
        json={
            "decision": "approve",
            "regression_id": result["id"],
            "reason": "Reviewed all fixture differences.",
        },
    )
    assert review.status_code == 200
    history = client.get(f"/api/detection-versions/{revision['id']}")
    assert history.status_code == 200
    assert history.json()["revision"]["status"] == "approved"
    assert len(history.json()["runs"]) == 2
    assert history.json()["review"]["reason"] == "Reviewed all fixture differences."
    current = client.get("/api/detections/APP-002/workbench").json()
    assert current["version"] == 2
    assert current["rule"]["threshold"] == 1500
    after = client.get("/api/replays/bulk-automation").json()
    assert after["final_state"]["alerts"] == []
    assert after["provenance"]["ruleset_digest"] == current["ruleset_digest"]
    assert after["provenance"]["ruleset_digest"] != before["provenance"]["ruleset_digest"]
    catalog = client.get("/api/detections").json()["items"]
    assert next(rule for rule in catalog if rule["id"] == "APP-002")["threshold"] == 1500


def test_regression_block_cannot_be_overridden_by_client_gate_or_approval(rule_client):
    created = proposal(rule_client, 2200)
    assert created.status_code == 201
    revision = created.json()
    run = rule_client.post(f"/api/detection-versions/{revision['id']}/regressions").json()
    assert run["result"]["gate"]["decision"] == "BLOCK"
    path = f"/api/detection-versions/{revision['id']}/review"
    spoofed = {
        "decision": "approve",
        "regression_id": run["id"],
        "reason": "Review",
        "gate": "PASS",
    }
    assert rule_client.post(path, json=spoofed).status_code == 422
    spoofed.pop("gate")
    assert rule_client.post(path, json=spoofed).status_code == 409
    assert rule_client.get("/api/detections/APP-002/workbench").json()["version"] == 1


@pytest.mark.parametrize(
    "parameters",
    [
        {"threshold": True},
        {"threshold": "1500"},
        {"expression": "arbitrary-code"},
        {"threshold": -1},
        {"window_minutes": 1},
    ],
)
def test_local_proposal_rejects_unsupported_or_untyped_parameters(rule_client, parameters):
    base = rule_client.get("/api/detections/APP-002/workbench")
    assert base.status_code == 200
    value = base.json()
    response = rule_client.post(
        "/api/detections/APP-002/versions",
        json={
            "parameters": parameters,
            "base_ruleset_digest": value["ruleset_digest"],
            "base_generation": value["generation"],
            "base_version": value["version"],
            "reason": "Review",
        },
    )
    assert response.status_code == 422
    assert rule_client.get("/api/detections/APP-002/workbench").json()["revision_count"] == 0


def test_predefined_comparisons_and_workbench_reads_leave_database_unchanged(
    scenario_client, scenario_database
):
    client, mode = scenario_client
    before = scenario_tests.database_snapshot(scenario_database)
    workbench = client.get("/api/detections/APP-002/workbench")
    assert workbench.status_code == 200
    assert workbench.json()["read_only"] is (mode == "public_demo")
    assert workbench.json()["version"] == 1
    for example_id, expected in (
        ("reduce-benign-volume", "PASS"),
        ("unchanged-volume", "WARN"),
        ("miss-service-access", "BLOCK"),
    ):
        response = client.get(f"/api/regressions/examples/{example_id}")
        assert response.status_code == 200
        assert response.json()["gate"]["decision"] == expected
        assert len(response.json()["scenarios"]) == 8
        assert len(response.content) <= 262144
        assert client.get(f"/api/regressions/examples/{example_id}").content == response.content
    assert client.get("/api/regressions/examples/unknown").status_code == 404
    assert (
        client.get("/api/regressions/examples/reduce-benign-volume?threshold=2200").status_code
        == 422
    )
    assert scenario_tests.database_snapshot(scenario_database) == before


def test_public_rule_mutations_are_denied_before_payload_processing(
    scenario_client, scenario_database
):
    client, mode = scenario_client
    before = scenario_tests.database_snapshot(scenario_database)
    for method, path in (
        ("POST", "/api/detections/APP-002/versions"),
        ("POST", "/api/detection-versions/REV-unknown/regressions"),
        ("POST", "/api/detection-versions/REV-unknown/review"),
        ("PATCH", "/api/detection-versions/REV-unknown"),
        ("DELETE", "/api/detection-versions/REV-unknown"),
    ):
        response = client.request(
            method, path, json={"arbitrary": "input"}, headers={"Origin": scenario_tests.ORIGIN}
        )
        if mode == "public_demo":
            assert response.status_code == 403
        else:
            assert response.status_code in {404, 405, 422}
    assert scenario_tests.database_snapshot(scenario_database) == before
