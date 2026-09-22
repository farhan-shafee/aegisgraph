"""Full-corpus synthetic measurements and explainable deterministic regression gates.

No model or replay playback is invoked. A proposal is evaluated against all rules,
including dependent rules, and independently authored scenario obligations.
"""

import hashlib
import json
import logging
from dataclasses import asdict
from functools import lru_cache
from time import perf_counter

from .correlation import correlate
from .detection import evaluate
from .rule_specs import ruleset_digest, validate_rules
from .scenario_ground_truth import ground_truth
from .scenarios import catalog, scenario_events

logger = logging.getLogger("aegisgraph.regressions")
MAX_CORPUS_EVENTS = 5000
MAX_SCENARIOS = 10
MAX_RESULT_BYTES = 262144


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


@lru_cache(maxsize=1)
def corpus_digest() -> str:
    """Bind both inert telemetry and independent labels to an immutable corpus revision."""
    digest = hashlib.sha256()
    for definition in catalog():
        payload = {
            "definition": definition,
            "events": [
                event.model_dump(mode="json") for event in scenario_events(definition["id"])
            ],
            "ground_truth": asdict(ground_truth(definition["id"])),
        }
        encoded = _canonical(payload)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _measure(
    rules: list[dict], selected_rule_id: str, corpus: list[tuple]
) -> tuple[list[dict], dict]:
    metrics = {
        "selected_rule": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "selected_rule_required_scenarios": 0,
        "selected_rule_benign_scenarios": 0,
        "selected_rule_other_scenarios": 0,
        "expected_detection_hits": 0,
        "required_detection_hits": 0,
        "required_detection_total": 0,
        "missed_required_detections": 0,
        "unexpected_detections": 0,
        "forbidden_detections": 0,
        "alert_count": 0,
        "benign_alert_count": 0,
        "incident_count": 0,
        "correlation_mismatches": 0,
        "detector_evaluations": 0,
    }
    rows = []
    for definition, events, truth in corpus:
        signals = evaluate(events, rules)
        metrics["detector_evaluations"] += 1
        cases = correlate(signals, events)
        actual = {signal.rule_id for signal in signals}
        required, expected, forbidden = map(
            set, (truth.required_rule_ids, truth.expected_rule_ids, truth.forbidden_rule_ids)
        )
        missing = required - actual
        unexpected = actual - expected
        denied = forbidden & actual
        correlation_matches = len(cases) == truth.expected_incident_count
        selected_hit = selected_rule_id in actual
        if selected_rule_id in required:
            metrics["selected_rule_required_scenarios"] += 1
            metrics["selected_rule"]["tp" if selected_hit else "fn"] += 1
        elif definition["classification"] == "benign":
            metrics["selected_rule_benign_scenarios"] += 1
            metrics["selected_rule"]["fp" if selected_hit else "tn"] += 1
        else:
            metrics["selected_rule_other_scenarios"] += 1
        metrics["expected_detection_hits"] += len(expected & actual)
        metrics["required_detection_hits"] += len(required & actual)
        metrics["required_detection_total"] += len(required)
        metrics["missed_required_detections"] += len(missing)
        metrics["unexpected_detections"] += len(unexpected)
        metrics["forbidden_detections"] += len(denied)
        metrics["alert_count"] += len(signals)
        metrics["benign_alert_count"] += (
            len(signals) if definition["classification"] == "benign" else 0
        )
        metrics["incident_count"] += len(cases)
        metrics["correlation_mismatches"] += int(not correlation_matches)
        rows.append(
            {
                "rule_ids": sorted(actual),
                "rule_match_counts": {
                    rule_id: sum(signal.rule_id == rule_id for signal in signals)
                    for rule_id in sorted(actual)
                },
                "alert_count": len(signals),
                "incident_count": len(cases),
                "missed_required_rule_ids": sorted(missing),
                "unexpected_rule_ids": sorted(unexpected),
                "forbidden_rule_ids": sorted(denied),
                "correlation_matches": correlation_matches,
            }
        )
    return rows, metrics


def compare_rulesets(baseline: list[dict], proposed: list[dict], selected_rule_id: str) -> dict:
    """Compute fixture results from two complete snapshots; never accept caller metrics."""
    start = perf_counter()
    before_rules = [rule.model_dump() for rule in validate_rules(baseline).rules]
    after_rules = [rule.model_dump() for rule in validate_rules(proposed).rules]
    baseline_by_id = {rule["id"]: rule for rule in before_rules}
    proposed_by_id = {rule["id"]: rule for rule in after_rules}
    selected_before, selected_after = (
        baseline_by_id[selected_rule_id],
        proposed_by_id[selected_rule_id],
    )
    if any(
        before != proposed_by_id[rule_id]
        for rule_id, before in baseline_by_id.items()
        if rule_id != selected_rule_id
    ):
        raise ValueError("A comparison may revise only the selected rule")
    changes = [
        {"parameter": name, "before": selected_before[name], "after": selected_after[name]}
        for name in ("threshold", "window_minutes")
        if selected_before[name] != selected_after[name]
    ]
    definitions = catalog()
    if not 1 <= len(definitions) <= MAX_SCENARIOS:
        raise ValueError("Scenario corpus exceeds the regression workload limit")
    if sum(item["event_count"] for item in definitions) > MAX_CORPUS_EVENTS:
        raise ValueError("Scenario corpus exceeds the regression event limit")
    corpus = [(item, scenario_events(item["id"]), ground_truth(item["id"])) for item in definitions]
    if sum(len(events) for _definition, events, _truth in corpus) > MAX_CORPUS_EVENTS:
        raise ValueError("Scenario corpus exceeds the regression event limit")
    before_rows, before_metrics = _measure(before_rules, selected_rule_id, corpus)
    after_rows, after_metrics = _measure(after_rules, selected_rule_id, corpus)
    rows, reasons = [], []
    regression_count = 0
    for (definition, _events, truth), before, after in zip(
        corpus, before_rows, after_rows, strict=True
    ):
        scenario_id = definition["id"]
        row = {
            "scenario_id": scenario_id,
            "classification": definition["classification"],
            "expected_rule_ids": list(truth.expected_rule_ids),
            "required_rule_ids": list(truth.required_rule_ids),
            "forbidden_rule_ids": list(truth.forbidden_rule_ids),
            "expected_incident_count": truth.expected_incident_count,
            "before": before,
            "after": after,
            "added_rule_ids": sorted(set(after["rule_ids"]) - set(before["rule_ids"])),
            "removed_rule_ids": sorted(set(before["rule_ids"]) - set(after["rule_ids"])),
        }
        rows.append(row)
        regression_count += len(
            set(after["missed_required_rule_ids"]) - set(before["missed_required_rule_ids"])
        )
        regression_count += len(
            set(after["forbidden_rule_ids"]) - set(before["forbidden_rule_ids"])
        )
        regression_count += int(before["correlation_matches"] and not after["correlation_matches"])
        for rule_id in after["missed_required_rule_ids"]:
            reasons.append(
                {
                    "code": "required_detection_missing",
                    "scenario_id": scenario_id,
                    "rule_id": rule_id,
                    "message": f"{rule_id} does not meet the required fixture detection in {scenario_id}.",
                }
            )
        for rule_id in after["forbidden_rule_ids"]:
            reasons.append(
                {
                    "code": "forbidden_detection",
                    "scenario_id": scenario_id,
                    "rule_id": rule_id,
                    "message": f"{rule_id} matches {scenario_id}, which explicitly forbids that detection.",
                }
            )
        if not after["correlation_matches"]:
            reasons.append(
                {
                    "code": "correlation_mismatch",
                    "scenario_id": scenario_id,
                    "message": f"{scenario_id} produced {after['incident_count']} incidents; its fixture requires {truth.expected_incident_count}.",
                }
            )
    if reasons:
        decision = "BLOCK"
    elif after_metrics["benign_alert_count"] > before_metrics["benign_alert_count"]:
        decision = "WARN"
        reasons.append(
            {
                "code": "benign_alert_burden_increased",
                "message": "The proposal increases alerts on labeled benign fixtures; human review is required.",
            }
        )
    elif (
        after_metrics["benign_alert_count"] < before_metrics["benign_alert_count"]
        or after_metrics["required_detection_hits"] > before_metrics["required_detection_hits"]
    ):
        decision = "PASS"
        reasons.append(
            {
                "code": "fixture_improvement",
                "message": "The proposal reduces benign-fixture alerts or restores required matches without violating fixture detection or correlation obligations.",
            }
        )
    else:
        decision = "WARN"
        reasons.append(
            {
                "code": "no_observed_improvement",
                "message": "The proposal shows no measured improvement in required matches or benign-fixture alert burden; human review is required.",
            }
        )
    result = {
        "selected_rule_id": selected_rule_id,
        "measurement_scope": "synthetic_fixture",
        "measurement_definitions": {
            "tp_fn": "TP/FN count matched/missed required scenarios for the selected rule.",
            "fp_tn": "FP/TN count selected-rule matches/nonmatches on explicitly benign scenarios only.",
            "other_scenarios": "Other scenarios are excluded from the selected-rule confusion matrix but still checked for forbidden matches and correlation invariants.",
            "expected_detection_hits": "Matches among the shipped v1 expected observations, including benign alerts. Losing an optional benign match can be desirable.",
            "required_coverage": "required_detection_hits / required_detection_total counts scenario-rule obligations, not a population estimate.",
            "regression_count": "New missing-required, forbidden-detection, and correlation violations compared with the baseline; the gate blocks any proposed-state violation.",
            "limits": "Synthetic fixture measurements only; not production detection accuracy, calibrated confidence, or security guarantees.",
        },
        "baseline_ruleset_digest": ruleset_digest(before_rules),
        "proposed_ruleset_digest": ruleset_digest(after_rules),
        "corpus_digest": corpus_digest(),
        "parameter_changes": changes,
        "metrics": {"before": before_metrics, "after": after_metrics},
        "scenarios": rows,
        "regression_count": regression_count,
        "gate": {"decision": decision, "reasons": reasons},
    }
    if len(_canonical(result)) > MAX_RESULT_BYTES:
        raise ValueError("Regression result exceeds its response limit")
    logger.info(
        json.dumps(
            {
                "operation": "detection_regression",
                "selected_rule_id": selected_rule_id,
                "scenarios": len(corpus),
                "events_processed": 2 * sum(len(events) for _definition, events, _truth in corpus),
                "detection_evaluations": before_metrics["detector_evaluations"]
                + after_metrics["detector_evaluations"],
                "correlation_evaluations": 2 * len(corpus),
                "duration_ms": round((perf_counter() - start) * 1000, 2),
            }
        )
    )
    return result
