"""Public replay is a bounded read projection, never a persisted visitor run."""

import re

import pytest
import test_scenario_api as scenario_support
from aegisgraph import analyst
from test_scenario_api import (
    ORIGIN,
    SCENARIO_IDS,
    database_snapshot,
)

# Reuse the real local/public application and isolated database fixtures.
scenario_client = scenario_support.scenario_client
scenario_database = scenario_support.scenario_database


@pytest.fixture(autouse=True)
def forbid_replay_provider_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Telemetry replay must not select or call an analyst provider")

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(analyst, "configured_provider", forbidden)
    monkeypatch.setattr(analyst.OpenAIProvider, "generate", forbidden)


def assert_no_evaluation_answer_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert key not in {
                "ground_truth",
                "answer_key",
                "supported_claim_types",
                "unsupported_claim_types",
                "required_rule_ids",
                "forbidden_rule_ids",
            }
            assert not key.startswith("expected_")
            assert_no_evaluation_answer_keys(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_evaluation_answer_keys(item)


def test_registered_replays_return_stable_bounded_projections_without_persistence(
    scenario_client, scenario_database
):
    client, _ = scenario_client
    # Snapshot before the first GET catches accidental lazy initialization too.
    before = database_snapshot(scenario_database)
    for scenario_id in sorted(SCENARIO_IDS):
        response = client.get(f"/api/replays/{scenario_id}")
        assert response.status_code == 200, scenario_id
        assert response.headers["content-type"].startswith("application/json")
        assert 0 < len(response.content) <= 1024 * 1024
        projection = response.json()
        assert projection["format_version"] == "1"
        assert projection["provenance"]["scenario_id"] == scenario_id
        assert projection["provenance"]["scenario_version"]
        assert re.fullmatch(r"[a-f0-9]{64}", projection["provenance"]["ruleset_digest"])
        assert 0 < len(projection["frames"]) <= 600
        assert projection["summary"]["frame_count"] == len(projection["frames"])
        assert projection["final_state"]["event_count"] == projection["summary"]["event_count"]
        assert_no_evaluation_answer_keys(projection)
        assert client.get(f"/api/replays/{scenario_id}").content == response.content
    assert database_snapshot(scenario_database) == before


def test_atlas_replay_carries_actual_completed_results_and_separate_initial_state(
    scenario_client, scenario_database
):
    client, _ = scenario_client
    before = database_snapshot(scenario_database)
    response = client.get("/api/replays/atlas-compromise")
    assert response.status_code == 200
    projection = response.json()
    assert projection["summary"]["event_count"] == 4026
    assert projection["summary"]["background_event_count"] == 4000
    assert projection["summary"]["playback_event_count"] == 26
    assert projection["initial_state"] == {
        "event_count": 4000,
        "alert_count": 0,
        "incident_count": 0,
    }
    result = projection["final_state"]
    assert len(result["alerts"]) == 10
    assert len(result["incidents"]) == 1
    assert result["incidents"][0]["id"] == "INC-fe8fa4b9508c"
    investigation = result["investigation"]
    assert investigation["id"] == "INC-fe8fa4b9508c"
    assert investigation["kind"] == "correlated_incident"
    assert investigation["incident_id"] == "INC-fe8fa4b9508c"
    assert len(investigation["evidence"]) == 26
    assert database_snapshot(scenario_database) == before


def test_uncorrelated_replay_retains_an_observation_scope_without_inventing_an_incident(
    scenario_client,
):
    client, _ = scenario_client
    response = client.get("/api/replays/isolated-anomaly")
    assert response.status_code == 200
    result = response.json()["final_state"]
    assert result["incidents"] == []
    investigation = result["investigation"]
    assert investigation["id"] == "SCOPE-isolated-anomaly"
    assert investigation["kind"] == "observation_scope"
    assert investigation["incident_id"] is None
    assert investigation["evidence"]
    assert all(
        item["incident_id"] == "SCOPE-isolated-anomaly" for item in investigation["evidence"]
    )


def test_unknown_replay_scenario_does_not_fall_back_or_echo_input(scenario_client):
    client, _ = scenario_client
    response = client.get("/api/replays/unknown-scenario")
    assert response.status_code == 404
    assert set(response.json()) == {"detail"}
    assert "unknown-scenario" not in response.text


def test_replay_rejects_caller_parameters_instead_of_accepting_events_seed_or_code(
    scenario_client, scenario_database
):
    client, _ = scenario_client
    before = database_snapshot(scenario_database)
    for parameter in ("events", "seed", "code", "scenario_id", "speed", "limit"):
        response = client.get(
            "/api/replays/atlas-compromise", params={parameter: "submitted-private-marker"}
        )
        assert response.status_code == 422, parameter
        assert set(response.json()) == {"detail"}
        assert "submitted-private-marker" not in response.text
    assert database_snapshot(scenario_database) == before


def test_public_replay_controls_cannot_create_or_reset_persisted_state(
    scenario_client, scenario_database
):
    client, mode = scenario_client
    before = database_snapshot(scenario_database)
    for method, path in (
        ("POST", "/api/replays"),
        ("POST", "/api/replays/atlas-compromise"),
        ("PUT", "/api/replays/atlas-compromise"),
        ("PATCH", "/api/replays/atlas-compromise"),
        ("DELETE", "/api/replays/atlas-compromise"),
        ("POST", "/api/replays/atlas-compromise/start"),
        ("POST", "/api/replays/atlas-compromise/reset"),
        ("POST", "/api/replays/reset"),
    ):
        response = client.request(
            method,
            path,
            headers={"Origin": ORIGIN},
            json={"events": [], "seed": 123},
        )
        if mode == "public_demo":
            assert response.status_code == 403, (method, path)
        else:
            assert response.status_code in {404, 405}, (method, path)
    assert database_snapshot(scenario_database) == before
