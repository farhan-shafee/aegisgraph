"""Feature discovery supports an additive frontend/backend rollout."""

import test_scenario_api as scenario_tests

scenario_client = scenario_tests.scenario_client
scenario_database = scenario_tests.scenario_database


def test_advertised_v2_reads_exist_without_changing_the_public_question_contract(scenario_client):
    client, mode = scenario_client
    runtime = client.get("/api/runtime").json()
    assert runtime["read_only"] is (mode == "public_demo")
    assert runtime["questions"] == ["What most likely happened?", "What malware family was used?"]
    for capability, path in (
        ("scenarios", "/api/scenarios"),
        ("replay", "/api/replays/isolated-anomaly"),
        ("rule_workbench", "/api/detections/APP-002/workbench"),
        ("hypotheses", "/api/incidents/INC-fe8fa4b9508c/hypotheses"),
        ("analyst_benchmark", "/api/evaluations/benchmark"),
        ("evidence_bundle", "/api/incidents/INC-fe8fa4b9508c/export"),
    ):
        assert runtime.get("capabilities", {}).get(capability) == 1
        assert client.get(path).status_code == 200
