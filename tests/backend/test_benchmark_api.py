"""The current benchmark is separate from stored legacy/live evaluation runs."""

import json
import sys
from types import SimpleNamespace

import pytest
import test_scenario_api as scenario_tests
from aegisgraph import cli

scenario_client = scenario_tests.scenario_client
scenario_database = scenario_tests.scenario_database


def test_benchmark_route_is_read_only_and_separate(scenario_client, scenario_database):
    client, _ = scenario_client
    before = scenario_tests.database_snapshot(scenario_database)
    legacy = client.get("/api/evaluations").json()
    response = client.get("/api/evaluations/benchmark")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] >= 100
    assert result["passed"] == result["total"]
    assert result["failed"] == 0
    assert result["live_model_tested"] is False
    assert result["provider"] == "deterministic"
    assert result["format_version"] == "1"
    assert len(response.content) <= 512 * 1024
    assert client.get("/api/evaluations/benchmark").json() == result
    assert client.get("/api/evaluations").json() == legacy
    assert scenario_tests.database_snapshot(scenario_database) == before


def test_benchmark_route_rejects_user_configuration(scenario_client):
    client, _ = scenario_client
    for query in ("?provider=openai", "?scenario=unknown", "?question=arbitrary"):
        response = client.get(f"/api/evaluations/benchmark{query}")
        assert response.status_code == 422
        assert "arbitrary" not in response.text


@pytest.mark.parametrize("failed", [0, 1])
@pytest.mark.parametrize("public", [False, True])
def test_benchmark_cli_uses_no_database_and_sets_exit_status(monkeypatch, capsys, failed, public):
    result = {"total": 2, "passed": 2 - failed, "failed": failed}
    monkeypatch.setitem(
        sys.modules, "aegisgraph.analyst_benchmark", SimpleNamespace(run_benchmark=lambda: result)
    )
    monkeypatch.setattr("sys.argv", ["aegisgraph", "evaluate-benchmark"])
    monkeypatch.setattr(cli, "settings", SimpleNamespace(public_demo=public))

    def forbidden():
        pytest.fail("Benchmark must not open a database session")

    monkeypatch.setattr(cli, "SessionLocal", forbidden)
    if failed:
        with pytest.raises(SystemExit) as failure:
            cli.main()
        assert failure.value.code == 1
    else:
        cli.main()
    assert json.loads(capsys.readouterr().out) == result
