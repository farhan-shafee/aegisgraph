"""Replay must be a causal projection of actual domain results, not a canned animation."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from threading import Lock

import pytest
from aegisgraph import replay
from aegisgraph import scenarios as corpus
from aegisgraph.correlation import correlate
from aegisgraph.detection import evaluate, load_rules
from aegisgraph.scenarios import catalog, scenario_events

SCENARIOS = [item["id"] for item in catalog()]


def test_atlas_initializes_only_normal_background_and_preserves_all_focus_events():
    projection = replay.replay_projection("atlas-compromise")
    assert projection["summary"]["event_count"] == 4026
    assert projection["summary"]["background_event_count"] == 4000
    assert projection["summary"]["playback_event_count"] == 26
    assert projection["initial_state"] == {
        "event_count": 4000,
        "alert_count": 0,
        "incident_count": 0,
    }
    assert not any(
        key in projection["provenance"]
        for key in ("incident_id", "expected_rule_ids", "ground_truth")
    )
    frame = projection["frames"][0]
    assert frame["seq"] == 0 and frame["stage"] == "context_initialized"
    assert frame["data"]["event_count"] == 4000
    focus_ids = [
        frame["event_id"] for frame in projection["frames"] if frame["stage"] == "telemetry"
    ]
    events = scenario_events("atlas-compromise")
    assert focus_ids == [
        event.event_id for event in events if event.event_id.startswith("EVT-SCENARIO-")
    ]
    background = [event for event in events if not event.event_id.startswith("EVT-SCENARIO-")]
    assert not evaluate(background)
    assert max(event.timestamp for event in background) < min(
        event.timestamp for event in events if event.event_id in focus_ids
    )


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_frames_are_bounded_ordered_and_return_fresh_nested_values(scenario_id):
    first = replay.replay_projection(scenario_id)
    second = replay.replay_projection(scenario_id)
    assert first == second and first is not second
    assert len(first["frames"]) <= 600
    assert len(json.dumps(first, separators=(",", ":"), ensure_ascii=False).encode()) <= 1_048_576
    assert [frame["seq"] for frame in first["frames"]] == list(range(len(first["frames"])))
    assert first["summary"]["frame_count"] == len(first["frames"])
    assert [frame["timestamp"] for frame in first["frames"]] == sorted(
        frame["timestamp"] for frame in first["frames"]
    )
    first["frames"][0]["data"]["caller_modified"] = True
    first["final_state"]["investigation"]["evidence"][0]["event"]["attributes"][
        "caller_modified"
    ] = True
    fresh = replay.replay_projection(scenario_id)
    assert "caller_modified" not in fresh["frames"][0]["data"]
    assert (
        "caller_modified"
        not in fresh["final_state"]["investigation"]["evidence"][0]["event"]["attributes"]
    )


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_final_state_matches_batch_detection_correlation_and_real_evidence(scenario_id):
    projection = replay.replay_projection(scenario_id)
    events = scenario_events(scenario_id)
    signals = evaluate(events)
    cases = correlate(signals, events)
    normalized = json.loads(json.dumps([asdict(signal) for signal in signals]))
    assert projection["final_state"]["alerts"] == normalized
    actual_cases = projection["final_state"]["incidents"]
    assert len(actual_cases) == len(cases)
    for actual, expected in zip(actual_cases, cases, strict=True):
        assert {key: actual[key] for key in asdict(expected)} == json.loads(
            json.dumps(asdict(expected))
        )
        assert actual["evidence_ids"] == [
            f"EVD-{hashlib.sha256(f'{expected.id}:{event_id}'.encode()).hexdigest()[:16]}"
            for event_id in expected.event_ids
        ]
    scope = projection["final_state"]["investigation"]
    assert scope["id"] == (cases[0].id if cases else f"SCOPE-{scenario_id}")
    assert scope["kind"] == ("correlated_incident" if cases else "observation_scope")
    assert scope["incident_id"] == (cases[0].id if cases else None)
    assert {row["event_id"] for row in scope["evidence"]} == (
        set(cases[0].event_ids) if cases else {event.event_id for event in events}
    )
    assert {row["incident_id"] for row in scope["evidence"]} == {scope["id"]}
    assert all(
        datetime.fromisoformat(row["timestamp"])
        == datetime.fromisoformat(row["event"]["timestamp"])
        for row in scope["evidence"]
    )
    assert projection["final_state"]["event_count"] == len(events)


def test_atlas_incident_changes_only_when_supporting_prefix_is_visible():
    projection = replay.replay_projection("atlas-compromise")
    changes = [frame for frame in projection["frames"] if frame["stage"] == "incident"]
    first = changes[0]
    assert first["timestamp"] == "2026-09-15T14:03:00+00:00"
    assert first["data"]["change"] == "created"
    assert first["data"]["incident"]["id"] == "INC-fe8fa4b9508c"
    assert first["data"]["incident"]["severity"] == "medium"
    assert "compromise" not in first["data"]["incident"]["title"].lower()
    assert set(first["data"]["incident"]["event_ids"]) == {
        "EVT-SCENARIO-001",
        "EVT-SCENARIO-002",
        "EVT-SCENARIO-003",
    }
    iam = [frame for frame in changes if frame["timestamp"] == "2026-09-15T14:07:00+00:00"]
    assert iam and all(frame["data"]["incident"]["severity"] == "medium" for frame in iam)
    sensitive = next(
        frame for frame in changes if frame["timestamp"] == "2026-09-15T14:14:00+00:00"
    )
    assert sensitive["data"]["incident"]["severity"] == "high"
    assert (
        sensitive["data"]["incident"]["title"] == "Suspected compromise of Atlas engineer account"
    )
    assert "EVT-SCENARIO-007" not in sensitive["data"]["incident"]["event_ids"]


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_alert_and_incident_frames_never_reference_future_telemetry(scenario_id):
    projection = replay.replay_projection(scenario_id)
    events = scenario_events(scenario_id)
    background = events[: projection["summary"]["background_event_count"]]
    seen_events = {event.event_id for event in background}
    seen_alerts = set()
    for frame in projection["frames"]:
        if frame["stage"] == "normalized":
            seen_events.add(frame["event_id"])
            assert frame["data"]["event"]["event_id"] == frame["event_id"]
        elif frame["stage"] in {"rule_match", "alert"}:
            assert set(frame["data"]["event_ids"]).issubset(seen_events)
            assert frame["event_id"] == frame["data"]["event_ids"][-1]
            if frame["stage"] == "alert":
                seen_alerts.add(frame["alert_id"])
        elif frame["stage"] == "incident":
            case = frame["data"]["incident"]
            assert set(case["event_ids"]).issubset(seen_events)
            assert set(case["alert_ids"]).issubset(seen_alerts)


@pytest.mark.parametrize("scenario_id", ["atlas-compromise", "service-access", "mixed-context"])
def test_completed_event_prefixes_agree_with_independent_batch_calls(scenario_id):
    projection = replay.replay_projection(scenario_id)
    events = scenario_events(scenario_id)
    observed = list(events[: projection["summary"]["background_event_count"]])
    by_id = {event.event_id: event for event in events}
    playback = [
        frame["event_id"] for frame in projection["frames"] if frame["stage"] == "telemetry"
    ]
    observed_alerts, observed_cases = [], {}
    for index, event_id in enumerate(playback):
        observed.append(by_id[event_id])
        for frame in (row for row in projection["frames"] if row.get("event_id") == event_id):
            if frame["stage"] == "alert":
                observed_alerts.append(frame["data"])
            elif frame["stage"] == "incident":
                observed_cases[frame["incident_id"]] = frame["data"]["incident"]
        if index in {0, 2, 3, len(playback) - 1}:
            batch_signals = evaluate(observed)
            batch_cases = correlate(batch_signals, observed)
            assert observed_alerts == json.loads(
                json.dumps([asdict(signal) for signal in batch_signals])
            )
            assert set(observed_cases) == {case.id for case in batch_cases}
            for case in batch_cases:
                assert observed_cases[case.id]["event_ids"] == list(case.event_ids)


def test_pure_projection_records_rule_digest_without_mutating_rules():
    baseline = load_rules()
    original = json.dumps(baseline, sort_keys=True)
    proposal = json.loads(original)
    next(rule for rule in proposal if rule["id"] == "APP-002")["threshold"] = 1500
    before = replay.build_projection("bulk-automation", baseline)
    after = replay.build_projection("bulk-automation", proposal)
    assert before["provenance"]["ruleset_digest"] != after["provenance"]["ruleset_digest"]
    assert len(before["final_state"]["alerts"]) == 1
    assert not after["final_state"]["alerts"]
    assert json.dumps(baseline, sort_keys=True) == original


def test_folded_background_cannot_hide_a_rule_match():
    proposal = load_rules()
    next(rule for rule in proposal if rule["id"] == "APP-002")["threshold"] = 1
    with pytest.raises(replay.ReplayLimitError, match="background"):
        replay.build_projection("atlas-compromise", proposal)


def test_atlas_without_an_incident_retains_only_declared_focus_evidence():
    rules = [rule for rule in load_rules() if rule["id"] == "APP-002"]
    rules[0]["threshold"] = 3000
    result = replay.build_projection("atlas-compromise", rules)
    assert not result["final_state"]["incidents"]
    scope = result["final_state"]["investigation"]
    assert scope["kind"] == "observation_scope" and scope["incident_id"] is None
    assert len(scope["evidence"]) == 26
    assert all(row["event_id"].startswith("EVT-SCENARIO-") for row in scope["evidence"])
    assert result["summary"]["background_event_count"] == 4000


def test_simultaneous_cold_requests_share_one_actual_detection_run(monkeypatch):
    replay._serialized_projection.cache_clear()
    corpus._serialized_events.cache_clear()
    original = replay.evaluate
    original_generate = corpus.generate_events
    counts = {"calls": 0, "generation": 0}
    count_lock = Lock()

    def counted_evaluate(events, rules):
        with count_lock:
            counts["calls"] += 1
        return original(events, rules)

    def counted_generate(*args, **kwargs):
        with count_lock:
            counts["generation"] += 1
        return original_generate(*args, **kwargs)

    monkeypatch.setattr(replay, "evaluate", counted_evaluate)
    monkeypatch.setattr(corpus, "generate_events", counted_generate)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(replay.replay_projection, ["atlas-compromise"] * 4))
    assert counts["calls"] == 1
    assert counts["generation"] == 1
    assert all(result == results[0] for result in results)


@pytest.mark.parametrize(
    "limit", ["MAX_FRAMES", "MAX_RESPONSE_BYTES", "MAX_EVENTS", "MAX_PLAYBACK_EVENTS"]
)
def test_projection_bounds_fail_closed(monkeypatch, limit):
    monkeypatch.setattr(replay, limit, 1)
    with pytest.raises(replay.ReplayLimitError):
        replay.build_projection("bulk-automation")


@pytest.mark.parametrize("limit", ["MAX_EVENTS", "MAX_PLAYBACK_EVENTS"])
def test_workload_limits_reject_before_running_detection(monkeypatch, limit):
    monkeypatch.setattr(replay, limit, 1)

    def no_detection(_events, _rules):
        pytest.fail("Oversized replay reached detection work")

    monkeypatch.setattr(replay, "evaluate", no_detection)
    with pytest.raises(replay.ReplayLimitError, match="workload"):
        replay.build_projection("bulk-automation")


@pytest.mark.parametrize("scenario_id", ["", "missing", "../atlas-compromise"])
def test_unknown_scenario_is_rejected_without_cache_fallback(scenario_id):
    with pytest.raises(KeyError):
        replay.replay_projection(scenario_id)
