"""Typed revisions may change only meaningful bounded detector parameters."""

import hashlib
import json

import pytest
from aegisgraph import rule_specs as specs
from aegisgraph.detection import load_rules
from pydantic import ValidationError


def test_baseline_preserves_existing_order_descriptions_and_replay_digest():
    baseline = specs.baseline_rules()
    assert baseline == load_rules()
    digest = hashlib.sha256(
        json.dumps(
            baseline, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()
    assert specs.ruleset_digest(baseline) == digest
    baseline[0]["threshold"] = 99
    assert specs.baseline_rules()[0]["threshold"] == 5


def test_proposal_is_complete_immutable_and_describes_effective_values():
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "APP-002", {"threshold": 1500})
    assert len(proposed) == 10 and baseline == load_rules()
    changed = [after for before, after in zip(baseline, proposed, strict=True) if before != after]
    assert len(changed) == 1 and changed[0]["id"] == "APP-002"
    assert changed[0]["threshold"] == 1500
    assert "1,500" in changed[0]["description"] and "1,000" not in changed[0]["description"]
    frozen = specs.validate_rules(proposed)
    with pytest.raises(ValidationError):
        frozen.rules[0].threshold = 15
    with pytest.raises(ValidationError):
        frozen.rules = ()


@pytest.mark.parametrize(
    "parameters",
    [
        {"threshold": True},
        {"threshold": "1500"},
        {"threshold": 1500.0},
        {"threshold": float("nan")},
        {"threshold": 0},
        {"threshold": 10001},
        {"threshold": None},
        {"window_minutes": 5},
        {"code": "return true"},
        {},
        {"threshold": 1000},
    ],
)
def test_invalid_or_ineffective_volume_parameters_are_rejected(parameters):
    with pytest.raises(ValueError):
        specs.propose_rules(specs.baseline_rules(), "APP-002", parameters)


@pytest.mark.parametrize(
    "rule_id,keys",
    [
        ("AUTH-001", {"threshold", "window_minutes"}),
        ("AUTH-002", {"threshold"}),
        ("AUTH-003", {"threshold"}),
        ("MFA-001", {"window_minutes"}),
        ("IAM-001", set()),
        ("IAM-002", {"window_minutes"}),
        ("IAM-003", {"window_minutes"}),
        ("API-001", {"threshold", "window_minutes"}),
        ("APP-001", set()),
        ("APP-002", {"threshold"}),
    ],
)
def test_parameter_metadata_exposes_only_effective_controls(rule_id, keys):
    fields = specs.rule_parameters(rule_id)
    assert {item["name"] for item in fields} == keys
    for field in fields:
        assert field["minimum"] <= field["default"] <= field["maximum"]
        assert field["step"] >= 1 and field["label"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "reordered",
        "unknown_kind",
        "wrong_kind",
        "bool",
        "extra",
        "stale_description",
        "renamed",
    ],
)
def test_complete_snapshot_validation_rejects_ambiguous_or_forged_definitions(mutation):
    rules = specs.baseline_rules()
    if mutation == "missing":
        rules.pop()
    elif mutation == "duplicate":
        rules[-1] = rules[0]
    elif mutation == "reordered":
        rules.reverse()
    elif mutation == "unknown_kind":
        rules[0]["kind"] = "custom_code"
    elif mutation == "wrong_kind":
        rules[0]["kind"] = "data_volume"
    elif mutation == "bool":
        rules[0]["threshold"] = True
    elif mutation == "extra":
        rules[0]["script"] = "untrusted"
    elif mutation == "stale_description":
        rules[0]["threshold"] = 6
    elif mutation == "renamed":
        rules[0]["name"] = "Not the registered rule"
    with pytest.raises(ValueError):
        specs.validate_rules(rules)


def test_updated_window_description_and_reversion_to_baseline_are_consistent():
    baseline = specs.baseline_rules()
    proposed = specs.propose_rules(baseline, "MFA-001", {"window_minutes": 2})
    assert "two" not in proposed[3]["description"]
    assert "2 minutes" in proposed[3]["description"]
    assert specs.propose_rules(proposed, "MFA-001", {"window_minutes": 5}) == baseline


@pytest.mark.parametrize("rule_id", ["missing", "APP-002;code", "../rules.json"])
def test_unknown_rule_ids_do_not_select_or_load_arbitrary_definitions(rule_id):
    with pytest.raises(KeyError):
        specs.rule_parameters(rule_id)
    with pytest.raises(KeyError):
        specs.propose_rules(specs.baseline_rules(), rule_id, {"threshold": 1500})


def test_existing_model_snapshots_are_revalidated_at_the_workflow_boundary():
    snapshot = specs.validate_rules(specs.baseline_rules())
    changed = snapshot.rules[0].model_copy(update={"threshold": True})
    forged = snapshot.model_copy(update={"rules": (changed, *snapshot.rules[1:])})
    with pytest.raises(ValueError):
        specs.validate_rules(forged)
