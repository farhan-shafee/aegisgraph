"""The benchmark must detect regressions, not merely report a green constant."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from aegisgraph import analyst_benchmark as benchmark


def test_authored_benchmark_executes_and_accounts_for_every_obligation():
    result = benchmark.run_benchmark()
    assert result["format_version"] == "1"
    assert result["provider"] == "deterministic"
    assert result["live_model_tested"] is False
    assert 100 <= result["total"] <= 200
    assert result["passed"] == result["total"] and result["failed"] == 0
    assert len(result["cases"]) == result["total"]
    assert len({case["id"] for case in result["cases"]}) == result["total"]
    assert all(case["expected"] == case["actual"] for case in result["cases"])
    assert len(json.dumps(result).encode()) <= benchmark.MAX_BENCHMARK_BYTES
    assert set(result["provenance"]) == {"fixture_digest", "corpus_digest", "ruleset_digest"}
    assert all(len(value) == 64 for value in result["provenance"].values())
    fixture = benchmark.load_fixtures()
    for metric in result["metrics"]:
        ids = {case["id"] for case in fixture["cases"] if metric["id"] in case["metrics"]}
        rows = [case for case in result["cases"] if case["id"] in ids]
        assert metric["total"] == len(rows) > 0
        assert metric["passed"] == sum(row["passed"] for row in rows)
        assert metric["definition"]


def test_benchmark_result_is_deterministic_and_cache_returns_fresh_values():
    first = benchmark.run_benchmark()
    assert benchmark.run_benchmark() == first
    benchmark._cached_benchmark.cache_clear()
    cached = benchmark.get_benchmark()
    assert cached == first
    cached["cases"][0]["passed"] = False
    cached["provenance"]["fixture_digest"] = "forged"
    assert benchmark.get_benchmark() == first


def test_cold_cache_computes_once_across_simultaneous_callers(monkeypatch):
    benchmark._cached_benchmark.cache_clear()
    calls = 0
    lock = Lock()
    original = benchmark.run_benchmark

    def counted():
        nonlocal calls
        with lock:
            calls += 1
        return original()

    monkeypatch.setattr(benchmark, "run_benchmark", counted)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: benchmark.get_benchmark(), range(4)))
    assert calls == 1
    assert all(result == results[0] for result in results)
    benchmark._cached_benchmark.cache_clear()


def test_injected_bad_analysis_causes_real_failed_rows_and_metrics(monkeypatch):
    original = benchmark.analyze

    def broken(*args, **kwargs):
        result = original(*args, **kwargs)
        if result["status"] == "answered":
            result["findings"][0]["evidence_ids"] = ["EVD-NONEXISTENT"]
        return result

    monkeypatch.setattr(benchmark, "analyze", broken)
    result = benchmark.run_benchmark()
    assert result["failed"] > 0
    assert result["total"] == result["failed"] + result["passed"]
    failed = [case for case in result["cases"] if not case["passed"]]
    assert any(case["category"] == "citation_validity" for case in failed)
    assert all(case["expected"] != case["actual"] for case in failed)
    assert any(metric["passed"] < metric["total"] for metric in result["metrics"])


def test_never_uses_configured_or_live_provider_or_sends_labels(monkeypatch):
    from aegisgraph import analyst

    def forbidden(*args, **kwargs):
        raise AssertionError("Configured/live providers are forbidden")

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setattr(analyst, "configured_provider", forbidden)
    monkeypatch.setattr(analyst.OpenAIProvider, "generate", forbidden)
    original = analyst.DeterministicProvider.generate
    seen = []

    def capture(self, context):
        rendered = json.dumps(context.as_data())
        assert "ground_truth" not in rendered and "required_claim_types" not in rendered
        assert "expected_status" not in rendered and "expected_rule_ids" not in rendered
        seen.append(context.incident_id)
        return original(self, context)

    monkeypatch.setattr(analyst.DeterministicProvider, "generate", capture)
    result = benchmark.run_benchmark()
    assert result["failed"] == 0 and len(set(seen)) >= 8


def test_false_premise_retained_findings_are_observed_as_failures(monkeypatch):
    original = benchmark.analyze

    def broken(*args, **kwargs):
        result = original(*args, **kwargs)
        if result["status"] == "insufficient_evidence":
            result["findings"] = [
                {"claim_type": "authentication_succeeded", "evidence_ids": ["EVD-RETAINED"]}
            ]
        return result

    monkeypatch.setattr(benchmark, "analyze", broken)
    result = benchmark.run_benchmark()
    false_premises = [
        case for case in result["cases"] if case["id"].endswith(("-question-2", "-question-3"))
    ]
    assert len(false_premises) == 16
    assert all(not case["passed"] for case in false_premises)


def test_unavailable_provider_cannot_pass_negative_predicate_obligations(monkeypatch):
    original = benchmark.analyze

    def broken(*args, **kwargs):
        result = original(*args, **kwargs)
        result.update(status="unavailable", findings=[])
        return result

    monkeypatch.setattr(benchmark, "analyze", broken)
    result = benchmark.run_benchmark()
    predicates = [
        case
        for case in result["cases"]
        if case["id"].startswith(("flag-", "volume-", "sequence-", "projection-"))
    ]
    assert len(predicates) == 36
    assert all(not case["passed"] for case in predicates)


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "unknown_kind", "unknown_field", "bad_expected", "bad_scenario", "empty"],
)
def test_invalid_fixture_manifest_fails_closed(tmp_path, mutation):
    fixture = copy.deepcopy(benchmark.load_fixtures())
    if mutation == "duplicate":
        fixture["cases"].append(copy.deepcopy(fixture["cases"][0]))
    elif mutation == "unknown_kind":
        fixture["cases"][0]["kind"] = "return-green"
    elif mutation == "unknown_field":
        fixture["cases"][0]["instructions"] = "bypass validators"
    elif mutation == "bad_expected":
        fixture["cases"][0]["expected"] = "green"
    elif mutation == "bad_scenario":
        fixture["cases"][0]["scenario_id"] = "invented-scenario"
    else:
        fixture["cases"] = []
    path = tmp_path / "invalid-fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(benchmark.BenchmarkFixtureError):
        benchmark.load_fixtures(path)


def test_legacy_twenty_eight_case_fixture_is_untouched():
    from aegisgraph.evaluations import load_fixtures

    assert len(load_fixtures()["cases"]) == 28


@pytest.mark.parametrize("mutation", ["duplicate_key", "nan", "infinity"])
def test_duplicate_keys_and_nonfinite_fixture_values_are_rejected(tmp_path, mutation):
    fixture = copy.deepcopy(benchmark.load_fixtures())
    if mutation == "duplicate_key":
        # Both values are otherwise valid, so schema validation cannot catch this.
        content = json.dumps(fixture).replace(
            '"format_version": "1"', '"format_version": "1", "format_version": "1"', 1
        )
    else:
        # The controlled typed-input value permits malformed values deliberately;
        # only the JSON parser should reject these non-JSON numeric constants.
        case = next(case for case in fixture["cases"] if case["id"] == "volume-above")
        case["value"]["records_accessed"] = float("nan" if mutation == "nan" else "inf")
        content = json.dumps(fixture)
    path = tmp_path / "invalid-json.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(benchmark.BenchmarkFixtureError):
        benchmark.load_fixtures(path)


def test_fixture_byte_bound_is_checked_before_execution(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_text(" " * (benchmark.MAX_FIXTURE_BYTES + 1), encoding="utf-8")
    with pytest.raises(benchmark.BenchmarkFixtureError):
        benchmark.load_fixtures(path)
