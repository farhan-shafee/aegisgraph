"""Export is a scoped read; verification stays on the caller's machine."""

import json
import sys
from types import SimpleNamespace

import pytest
import test_scenario_api as scenario_tests
from aegisgraph import cli

scenario_client = scenario_tests.scenario_client
scenario_database = scenario_tests.scenario_database
CASE = "INC-fe8fa4b9508c"
PATH = f"/api/incidents/{CASE}/export"


def test_export_is_bounded_hash_verifiable_and_does_not_persist(scenario_client, scenario_database):
    client, mode = scenario_client
    before = scenario_tests.database_snapshot(scenario_database)
    response = client.get(PATH)
    assert response.status_code == 200
    from aegisgraph.evidence_bundle import MAX_BUNDLE_BYTES, verify_bundle

    bundle = response.json()
    assert len(response.content) <= MAX_BUNDLE_BYTES
    assert verify_bundle(bundle)["status"] == "VALID"
    assert bundle["manifest"]["incident_id"] == CASE
    assert bundle["manifest"]["scenario_id"] == "atlas-compromise"
    assert bundle["manifest"]["projection"] == (
        "public_synthetic" if mode == "public_demo" else "local_review"
    )
    assert len(bundle["manifest"]["evidence_ids"]) == 26
    assert scenario_tests.database_snapshot(scenario_database) == before


def test_export_rejects_arbitrary_options_and_unknown_scopes(scenario_client):
    client, _ = scenario_client
    for query in ("?path=../../private", "?include=all", "?generated_at=2026-01-01"):
        response = client.get(PATH + query)
        assert response.status_code == 422
        assert "private" not in response.text
    assert client.get("/api/incidents/INC-UNKNOWN/export").status_code == 404
    assert client.get("/api/incidents/SCOPE-isolated-anomaly/export").status_code in {404, 422}


@pytest.mark.parametrize(
    "status", ["VALID", "MODIFIED", "MISSING FILE", "UNEXPECTED FILE", "INVALID"]
)
def test_verifier_cli_reads_bounded_bytes_without_a_database(monkeypatch, tmp_path, capsys, status):
    path = tmp_path / "bundle.json"
    path.write_bytes(b'{"synthetic":"fixture"}')
    observed = []
    result = {"status": status, "findings": [], "checked_files": 1, "limitations": []}

    def verify(value):
        observed.append(value)
        return result

    monkeypatch.setitem(
        sys.modules,
        "aegisgraph.evidence_bundle",
        SimpleNamespace(MAX_BUNDLE_BYTES=1024, verify_bundle=verify),
    )
    monkeypatch.setattr("sys.argv", ["aegisgraph", "verify-bundle", str(path)])
    monkeypatch.setattr(cli, "settings", SimpleNamespace(public_demo=True))
    monkeypatch.setattr(
        cli, "SessionLocal", lambda: pytest.fail("Verifier must not query a database")
    )
    if status == "VALID":
        cli.main()
    else:
        with pytest.raises(SystemExit) as failure:
            cli.main()
        assert failure.value.code == 1
    assert observed == [path.read_bytes()]
    assert json.loads(capsys.readouterr().out) == result


def test_verifier_cli_read_failure_is_sanitized(monkeypatch, tmp_path, capsys):
    private_path = tmp_path / "private-local-path.json"
    monkeypatch.setattr("sys.argv", ["aegisgraph", "verify-bundle", str(private_path)])
    with pytest.raises(SystemExit) as failure:
        cli.main()
    assert failure.value.code != 0
    output = capsys.readouterr()
    assert "Bundle file could not be read" in output.err
    assert str(private_path) not in output.out + output.err


def test_verifier_cli_does_not_read_an_unbounded_file(monkeypatch, tmp_path, capsys):
    path = tmp_path / "large.json"
    path.write_bytes(b"x" * 100)
    observed = []

    def verify(value):
        observed.append(len(value))
        return {"status": "INVALID"}

    monkeypatch.setitem(
        sys.modules,
        "aegisgraph.evidence_bundle",
        SimpleNamespace(MAX_BUNDLE_BYTES=8, verify_bundle=verify),
    )
    monkeypatch.setattr("sys.argv", ["aegisgraph", "verify-bundle", str(path)])
    with pytest.raises(SystemExit) as failure:
        cli.main()
    assert failure.value.code == 1
    assert observed == [9]
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID"
