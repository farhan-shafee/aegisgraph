"""Decision receipts must describe the actual principal/window qualification."""

from datetime import UTC, datetime, timedelta
from itertools import permutations

import pytest
from aegisgraph import correlation
from aegisgraph.detection import Signal, evaluate
from aegisgraph.scenarios import scenario_events

START = datetime(2026, 9, 15, 14, tzinfo=UTC)


def signal(number, rule_id, minutes=0, *, user="USR-RECEIPT", timestamp=None):
    return Signal(
        f"ALT-RECEIPT-{number}",
        rule_id,
        "Synthetic receipt signal",
        "medium",
        "Synthetic receipt test",
        timestamp or (START + timedelta(minutes=minutes)).isoformat(),
        user,
        (f"EVT-RECEIPT-{number}",),
    )


def decisions(signals):
    return correlation.correlate_with_decisions(signals, [])


def test_empty_input_has_no_invented_principal_or_decision():
    assert decisions([]) == ([], [])


def test_approved_administration_receipt_exposes_both_unmet_minimums():
    events = scenario_events("approved-admin")
    cases, receipts = decisions(evaluate(events))
    assert cases == []
    assert receipts == [
        {
            "policy_version": "principal-window-v1",
            "principal_id": "USR-approved-admin",
            "alert_ids": [item.id for item in evaluate(events)],
            "rule_ids": ["IAM-001", "IAM-003"],
            "rule_families": ["IAM"],
            "first_alert_at": "2026-09-15T14:01:00+00:00",
            "last_alert_at": "2026-09-15T14:10:00+00:00",
            "window_end_at": "2026-09-15T14:31:00+00:00",
            "span_minutes": 9,
            "window_minutes": 30,
            "minimum_rules": 3,
            "minimum_families": 2,
            "unmet_conditions": ["distinct_rules", "rule_families"],
            "incident_id": None,
        }
    ]


def test_repeated_rule_matches_do_not_satisfy_distinct_rule_minimum():
    cases, receipts = decisions(
        [signal(1, "IAM-001"), signal(2, "IAM-001", 1), signal(3, "APP-001", 2)]
    )
    assert cases == []
    assert receipts[0]["rule_ids"] == ["APP-001", "IAM-001"]
    assert receipts[0]["unmet_conditions"] == ["distinct_rules"]


def test_principals_do_not_combine_rule_diversity():
    cases, receipts = decisions(
        [signal(1, "IAM-001"), signal(2, "IAM-002", 1), signal(3, "APP-001", 2, user="OTHER")]
    )
    assert cases == []
    assert [(row["principal_id"], row["rule_ids"]) for row in receipts] == [
        ("OTHER", ["APP-001"]),
        ("USR-RECEIPT", ["IAM-001", "IAM-002"]),
    ]
    assert all(row["unmet_conditions"] == ["distinct_rules", "rule_families"] for row in receipts)


def test_windows_remain_disjoint_and_anchored_to_first_alert():
    # The last three alerts fit a sliding window; that is deliberately not this policy.
    cases, receipts = decisions(
        [
            signal(1, "IAM-001", 0),
            signal(2, "IAM-001", 20),
            signal(3, "APP-001", 31),
            signal(4, "AUTH-002", 40),
        ]
    )
    assert cases == []
    assert [row["alert_ids"] for row in receipts] == [
        ["ALT-RECEIPT-1", "ALT-RECEIPT-2"],
        ["ALT-RECEIPT-3", "ALT-RECEIPT-4"],
    ]
    assert [row["span_minutes"] for row in receipts] == [20, 9]
    assert [row["window_end_at"] for row in receipts] == [
        "2026-09-15T14:30:00+00:00",
        "2026-09-15T15:01:00+00:00",
    ]


@pytest.mark.parametrize("last_minute,incident_count,cluster_count", [(30, 1, 1), (30.0001, 0, 2)])
def test_window_is_inclusive_at_exact_thirty_minutes(last_minute, incident_count, cluster_count):
    cases, receipts = decisions(
        [signal(1, "AUTH-002"), signal(2, "IAM-001", 20), signal(3, "APP-001", last_minute)]
    )
    assert len(cases) == incident_count
    assert len(receipts) == cluster_count
    assert [row["incident_id"] for row in receipts if row["incident_id"]] == [
        case.id for case in cases
    ]
    assert all(bool(row["unmet_conditions"]) is (row["incident_id"] is None) for row in receipts)


def test_receipt_orders_real_instants_and_serializes_window_in_utc():
    cases, receipts = decisions(
        [
            signal(3, "APP-001", timestamp="2026-09-15T16:30:00+02:00"),
            signal(1, "AUTH-002", timestamp="2026-09-15T10:00:00-04:00"),
            signal(2, "IAM-001", timestamp="2026-09-15T14:20:00+00:00"),
        ]
    )
    assert len(cases) == 1
    assert receipts[0]["first_alert_at"] == "2026-09-15T14:00:00+00:00"
    assert (
        receipts[0]["last_alert_at"] == receipts[0]["window_end_at"] == "2026-09-15T14:30:00+00:00"
    )
    assert receipts[0]["span_minutes"] == 30


def test_equal_time_permutations_preserve_cases_and_receipts():
    rows = [
        signal(2, "AUTH-002"),
        signal(1, "AUTH-002"),
        signal(3, "IAM-001"),
        signal(4, "APP-001"),
    ]
    expected_cases, expected_receipts = decisions(rows)
    assert len(expected_cases) == 1
    assert expected_receipts[0]["alert_ids"] == [
        "ALT-RECEIPT-4",
        "ALT-RECEIPT-1",
        "ALT-RECEIPT-2",
        "ALT-RECEIPT-3",
    ]
    for ordered in permutations(rows):
        assert correlation.correlate(list(ordered), []) == expected_cases
        assert decisions(list(ordered)) == (expected_cases, expected_receipts)


@pytest.mark.parametrize(
    "scenario_id,expected_ids",
    [
        ("atlas-compromise", ["INC-fe8fa4b9508c"]),
        ("auth-pressure", ["INC-d206874f3d81"]),
        ("service-access", ["INC-1b31ae5acc8e"]),
        ("sensitive-enumeration", []),
        ("approved-admin", []),
        ("bulk-automation", []),
        ("isolated-anomaly", []),
        ("mixed-context", ["INC-920ad7d6e8a3"]),
    ],
)
def test_corpus_case_identity_is_preserved_under_signal_reversal(scenario_id, expected_ids):
    events = scenario_events(scenario_id)
    rows = evaluate(events)
    cases = correlation.correlate(rows, events)
    assert [case.id for case in cases] == expected_ids
    assert correlation.correlate(list(reversed(rows)), events) == cases
