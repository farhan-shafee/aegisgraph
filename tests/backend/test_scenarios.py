"""Corpus contracts use independently specified synthetic outcomes, not observed answers."""

import json
from dataclasses import FrozenInstanceError

import pytest
from aegisgraph import scenarios
from aegisgraph.analyst import DeterministicProvider, analyze, build_context
from aegisgraph.correlation import correlate
from aegisgraph.detection import evaluate
from aegisgraph.generator import generate_events
from aegisgraph.scenario_ground_truth import ground_truth

EXPECTED = {
    "atlas-compromise": (
        {
            "AUTH-002",
            "AUTH-003",
            "MFA-001",
            "IAM-001",
            "IAM-002",
            "API-001",
            "APP-001",
            "APP-002",
            "IAM-003",
        },
        1,
    ),
    "auth-pressure": ({"AUTH-001", "AUTH-002", "AUTH-003", "MFA-001"}, 1),
    "service-access": ({"API-001", "APP-001", "APP-002"}, 1),
    "sensitive-enumeration": ({"API-001", "APP-001"}, 0),
    "approved-admin": ({"IAM-001", "IAM-003"}, 0),
    "bulk-automation": ({"APP-002"}, 0),
    "isolated-anomaly": ({"AUTH-002"}, 0),
    "mixed-context": (
        {"AUTH-002", "AUTH-003", "MFA-001", "IAM-001", "IAM-002", "APP-001", "IAM-003"},
        1,
    ),
}
RULE_IDS = {
    "AUTH-001",
    "AUTH-002",
    "AUTH-003",
    "MFA-001",
    "IAM-001",
    "IAM-002",
    "IAM-003",
    "API-001",
    "APP-001",
    "APP-002",
}
SUPPORTED = {
    "atlas-compromise": {
        "authentication_succeeded",
        "unrecognized_authentication",
        "mfa_accepted",
        "privilege_assigned",
        "api_enumeration",
        "sensitive_access",
        "high_volume_access",
        "second_device_session",
        "privilege_reverted",
        "suspicious_sequence",
    },
    "auth-pressure": {"authentication_succeeded", "unrecognized_authentication", "mfa_accepted"},
    "service-access": {"sensitive_access", "high_volume_access"},
    "sensitive-enumeration": {"authentication_succeeded", "sensitive_access"},
    "approved-admin": {"authentication_succeeded", "privilege_assigned", "privilege_reverted"},
    "bulk-automation": {"authentication_succeeded", "high_volume_access"},
    "isolated-anomaly": {
        "authentication_succeeded",
        "unrecognized_authentication",
        "second_device_session",
    },
    "mixed-context": {
        "authentication_succeeded",
        "unrecognized_authentication",
        "mfa_accepted",
        "privilege_assigned",
        "sensitive_access",
        "second_device_session",
        "privilege_reverted",
        "suspicious_sequence",
    },
}


def test_catalog_is_metadata_only_and_matches_available_scenarios():
    items = scenarios.catalog()
    assert [item["id"] for item in items] == list(EXPECTED)
    for item in items:
        assert set(item) == {
            "id",
            "version",
            "title",
            "classification",
            "purpose",
            "theme",
            "event_count",
            "canonical_incident_id",
        }
        assert item["event_count"] == len(scenarios.scenario_events(item["id"]))
        assert item["purpose"] and item["theme"]
        assert item == scenarios.scenario_definition(item["id"])
    items[0]["title"] = "Changed by caller"
    assert scenarios.catalog()[0]["title"] != "Changed by caller"


def test_atlas_preserves_existing_telemetry_and_case_identifiers():
    events = scenarios.scenario_events("atlas-compromise")
    assert events == generate_events(seed=42)
    assert len(events) == 4026
    assert correlate(evaluate(events), events)[0].id == "INC-fe8fa4b9508c"
    assert (
        scenarios.scenario_definition("atlas-compromise")["canonical_incident_id"]
        == "INC-fe8fa4b9508c"
    )


@pytest.mark.parametrize("scenario_id", EXPECTED)
def test_each_scenario_matches_independently_specified_rules_and_correlation(scenario_id):
    events = scenarios.scenario_events(scenario_id)
    signals = evaluate(events)
    expected_rules, expected_incidents = EXPECTED[scenario_id]
    assert {signal.rule_id for signal in signals} == expected_rules
    assert len(correlate(signals, events)) == expected_incidents
    truth = ground_truth(scenario_id)
    assert set(truth.expected_rule_ids) == expected_rules
    assert set(truth.forbidden_rule_ids) == RULE_IDS - expected_rules
    assert truth.expected_incident_count == expected_incidents
    assert set(truth.required_rule_ids).issubset(expected_rules)
    if scenario_id in {"approved-admin", "bulk-automation"}:
        assert not truth.required_rule_ids
    else:
        assert set(truth.required_rule_ids) == expected_rules


@pytest.mark.parametrize("scenario_id", EXPECTED)
def test_generation_is_ordered_fresh_synthetic_and_has_no_answer_key(scenario_id):
    first = scenarios.scenario_events(scenario_id)
    second = scenarios.scenario_events(scenario_id)
    assert first == second and first is not second
    assert [(event.timestamp, event.event_id) for event in first] == sorted(
        (event.timestamp, event.event_id) for event in first
    )
    assert len({event.event_id for event in first}) == len(first)
    assert all(event.raw["synthetic"] for event in first)
    encoded = json.dumps([event.model_dump(mode="json") for event in first])
    for forbidden in (
        "expected_rule_ids",
        "expected_incident_count",
        "supported_claim_types",
        "ground_truth",
    ):
        assert forbidden not in encoded
    first[0].attributes["caller_mutation"] = {"nested": "changed"}
    first[0].raw["synthetic"] = False
    fresh = scenarios.scenario_events(scenario_id)
    assert "caller_mutation" not in fresh[0].attributes
    assert fresh[0].raw["synthetic"] is True


def test_scenario_principals_and_event_ids_do_not_overlap():
    seen_events, seen_principals = set(), set()
    for scenario_id in EXPECTED:
        events = scenarios.scenario_events(scenario_id)
        event_ids = {event.event_id for event in events}
        principals = {event.actor.user_id for event in events}
        assert not seen_events.intersection(event_ids)
        assert not seen_principals.intersection(principals)
        seen_events.update(event_ids)
        seen_principals.update(principals)
        if scenario_id != "atlas-compromise":
            assert len(events) <= 80
            assert all(event.event_id.startswith(f"EVT-{scenario_id}-") for event in events)


@pytest.mark.parametrize("scenario_id", EXPECTED)
def test_ground_truth_has_real_evidence_and_explicit_claim_and_question_limits(scenario_id):
    truth = ground_truth(scenario_id)
    events = scenarios.scenario_events(scenario_id)
    assert set(truth.relevant_event_ids).issubset({event.event_id for event in events})
    assert truth.relevant_event_ids and truth.evidence_categories
    assert truth.security_hypothesis and truth.not_established
    assert set(truth.supported_claim_types).isdisjoint(truth.unsupported_claim_types)
    assert {"malware_attribution", "external_exfiltration", "verified_actor_attribution"}.issubset(
        truth.unsupported_claim_types
    )
    malware = next(
        item for item in truth.questions if item.question == "What malware family was used?"
    )
    assert malware.expected_status == "insufficient_evidence"
    assert not malware.required_claim_types
    with pytest.raises(FrozenInstanceError):
        truth.expected_incident_count = 999


def test_benign_and_mixed_fixtures_include_observations_not_just_labels():
    for scenario_id in ("approved-admin", "bulk-automation", "mixed-context"):
        truth = ground_truth(scenario_id)
        assert truth.benign_observations
        assert any(
            event.event_type in {"change_context", "automation_context"}
            for event in scenarios.scenario_events(scenario_id)
        )
    bulk = scenarios.scenario_events("bulk-automation")
    assert any(event.attributes.get("records_accessed") == 1200 for event in bulk)
    service = scenarios.scenario_events("service-access")
    assert any(event.attributes.get("records_accessed") == 1800 for event in service)


@pytest.mark.parametrize("scenario_id", EXPECTED)
def test_declared_claim_support_matches_bounded_case_evidence(scenario_id):
    events = scenarios.scenario_events(scenario_id)
    cases = correlate(evaluate(events), events)
    allowed_events = set(cases[0].event_ids) if cases else {event.event_id for event in events}
    incident_id = cases[0].id if cases else f"INC-REVIEW-{scenario_id}"
    evidence = [
        {
            "id": f"EVD-TEST-{index}",
            "incident_id": incident_id,
            "event_id": event.event_id,
            "relevance": "unreviewed",
            "event": event.model_dump(mode="json"),
        }
        for index, event in enumerate(events)
        if event.event_id in allowed_events
    ]
    context = build_context(
        "What most likely happened?", incident_id, evidence, allowed_incident_ids={incident_id}
    )
    actual = {claim["claim_type"] for claim in context.supported_claims}
    assert actual == SUPPORTED[scenario_id]
    truth = ground_truth(scenario_id)
    assert set(truth.supported_claim_types) == SUPPORTED[scenario_id]
    assert all(set(question.required_claim_types).issubset(actual) for question in truth.questions)
    for question in truth.questions:
        result = analyze(
            question.question,
            incident_id,
            evidence,
            allowed_incident_ids={incident_id},
            provider=DeterministicProvider(),
        )
        assert result["status"] == question.expected_status
        assert set(question.required_claim_types).issubset(
            finding["claim_type"] for finding in result["findings"]
        )


@pytest.mark.parametrize("unknown", ["", "missing", "../atlas-compromise", "ATLAS-COMPROMISE"])
def test_unknown_scenario_does_not_fall_back_or_resolve_a_path(unknown):
    for getter in (
        scenarios.scenario_definition,
        scenarios.scenario_events,
        ground_truth,
    ):
        with pytest.raises(KeyError):
            getter(unknown)
