"""Fixture regressions compute outcomes; public examples have no canned scores."""

import json
from dataclasses import replace

import pytest
from aegisgraph import regressions
from aegisgraph import rule_specs as specs


@pytest.mark.parametrize(
    "threshold,decision,tp,fp,fn",
    [(1500, "PASS", 2, 0, 0), (1100, "WARN", 2, 1, 0), (2200, "BLOCK", 1, 0, 1)],
)
def test_volume_examples_are_measured_from_all_eight_scenarios(threshold, decision, tp, fp, fn):
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "APP-002", {"threshold": threshold})
    result = regressions.compare_rulesets(baseline, proposed, "APP-002")
    assert result["measurement_scope"] == "synthetic_fixture"
    assert result["gate"]["decision"] == decision
    assert result["gate"]["reasons"]
    assert len(result["scenarios"]) == 8
    assert result["metrics"]["before"]["selected_rule"] == {"tp": 2, "fp": 1, "fn": 0, "tn": 1}
    assert result["metrics"]["after"]["selected_rule"] == {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": 2 - fp,
    }
    assert result["metrics"]["after"]["selected_rule_required_scenarios"] == 2
    assert result["metrics"]["after"]["selected_rule_benign_scenarios"] == 2
    assert result["metrics"]["after"]["selected_rule_other_scenarios"] == 4
    assert result["parameter_changes"] == [
        {"parameter": "threshold", "before": 1000, "after": threshold}
    ]
    bulk = next(row for row in result["scenarios"] if row["scenario_id"] == "bulk-automation")
    assert bulk["before"]["rule_ids"] == ["APP-002"]
    assert bulk["after"]["rule_ids"] == (["APP-002"] if threshold == 1100 else [])
    service = next(row for row in result["scenarios"] if row["scenario_id"] == "service-access")
    if threshold == 2200:
        assert service["after"]["missed_required_rule_ids"] == ["APP-002"]
        assert service["before"]["incident_count"] == 1 and service["after"]["incident_count"] == 0
        assert {reason["code"] for reason in result["gate"]["reasons"]} >= {
            "required_detection_missing",
            "correlation_mismatch",
        }


def test_auth_novelty_revision_measures_dependent_rules_in_full_ruleset():
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "AUTH-002", {"threshold": 5})
    result = regressions.compare_rulesets(baseline, proposed, "AUTH-002")
    assert result["gate"]["decision"] == "BLOCK"
    auth = next(row for row in result["scenarios"] if row["scenario_id"] == "auth-pressure")
    assert {"AUTH-002", "MFA-001"}.issubset(auth["removed_rule_ids"])
    mixed = next(row for row in result["scenarios"] if row["scenario_id"] == "mixed-context")
    assert {"AUTH-002", "MFA-001", "IAM-002"}.issubset(mixed["removed_rule_ids"])


def test_earlier_trigger_revision_evaluates_all_scenarios_without_replay_shortcuts():
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "API-001", {"threshold": 2})
    result = regressions.compare_rulesets(baseline, proposed, "API-001")
    assert result["metrics"]["after"]["detector_evaluations"] == 8
    assert result["gate"]["decision"] in {"WARN", "BLOCK"}
    # This threshold shifts the first alert to the second endpoint, not a canned final-step trigger.
    enumeration = next(
        row for row in result["scenarios"] if row["scenario_id"] == "sensitive-enumeration"
    )
    assert enumeration["after"]["alert_count"] >= 2


def test_results_and_digests_are_repeatable_without_shared_mutable_results():
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "APP-002", {"threshold": 1500})
    first = regressions.compare_rulesets(baseline, proposed, "APP-002")
    second = regressions.compare_rulesets(baseline, proposed, "APP-002")
    assert first == second
    assert first["baseline_ruleset_digest"] == specs.ruleset_digest(baseline)
    assert first["proposed_ruleset_digest"] == specs.ruleset_digest(proposed)
    assert first["corpus_digest"] == regressions.corpus_digest()
    assert len(first["corpus_digest"]) == 64
    first["scenarios"][0]["after"]["rule_ids"].append("FORGED")
    assert "FORGED" not in second["scenarios"][0]["after"]["rule_ids"]
    assert "duration_ms" not in json.dumps(second)


def test_selected_rule_does_not_hide_other_proposed_changes():
    baseline = specs.baseline_rules()
    changed = specs.propose_rules(baseline, "APP-002", {"threshold": 1500})
    changed = specs.propose_rules(changed, "API-001", {"threshold": 15})
    with pytest.raises(ValueError):
        regressions.compare_rulesets(baseline, changed, "APP-002")


def test_forbidden_benign_detection_and_new_incident_block_a_candidate(monkeypatch):
    original_events = regressions.scenario_events

    def maintenance_with_two_endpoints(scenario_id):
        events = original_events(scenario_id)
        if scenario_id == "approved-admin":
            request = next(event for event in events if event.action == "request")
            second = request.model_copy(
                update={
                    "event_id": "EVT-approved-admin-second-maintenance-request",
                    "target": request.target.model_copy(
                        update={"endpoint": "/internal/v1/maintenance/status"}
                    ),
                },
                deep=True,
            )
            events.append(second)
            events.sort(key=lambda event: (event.timestamp, event.event_id))
        return events

    monkeypatch.setattr(regressions, "scenario_events", maintenance_with_two_endpoints)
    regressions.corpus_digest.cache_clear()
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "API-001", {"threshold": 2})
    try:
        result = regressions.compare_rulesets(baseline, proposed, "API-001")
    finally:
        regressions.corpus_digest.cache_clear()
    admin = next(row for row in result["scenarios"] if row["scenario_id"] == "approved-admin")
    assert admin["before"]["incident_count"] == 0
    assert admin["after"]["incident_count"] == 1
    assert admin["after"]["forbidden_rule_ids"] == ["API-001"]
    assert result["gate"]["decision"] == "BLOCK"
    assert {reason["code"] for reason in result["gate"]["reasons"]} >= {
        "forbidden_detection",
        "correlation_mismatch",
    }
    assert result["metrics"]["after"]["selected_rule"]["fp"] == 1


@pytest.mark.parametrize("component", ["version", "telemetry", "ground_truth"])
def test_corpus_digest_changes_when_any_provenance_component_changes(monkeypatch, component):
    regressions.corpus_digest.cache_clear()
    before = regressions.corpus_digest()
    if component == "version":
        original = regressions.catalog

        def altered_catalog():
            items = original()
            items[0]["version"] = "2"
            return items

        monkeypatch.setattr(regressions, "catalog", altered_catalog)
    elif component == "telemetry":
        original = regressions.scenario_events

        def altered_events(scenario_id):
            events = original(scenario_id)
            if scenario_id == "bulk-automation":
                events[0].attributes["synthetic_provenance_change"] = True
            return events

        monkeypatch.setattr(regressions, "scenario_events", altered_events)
    else:
        original = regressions.ground_truth

        def altered_truth(scenario_id):
            truth = original(scenario_id)
            return (
                replace(truth, security_hypothesis="Changed synthetic evaluation expectation")
                if scenario_id == "bulk-automation"
                else truth
            )

        monkeypatch.setattr(regressions, "ground_truth", altered_truth)
    regressions.corpus_digest.cache_clear()
    try:
        assert regressions.corpus_digest() != before
    finally:
        regressions.corpus_digest.cache_clear()
