"""Bounded causal telemetry projections with no visitor sessions or persistent writes.

The detector is causal and runs once per projection. A signal is released only at
its last supporting event. Correlation then sees the observed prefix, never the
completed scenario. Playback controls are a client cursor over these real frames.
"""

import copy
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import asdict
from functools import lru_cache
from threading import Lock
from time import perf_counter

from .correlation import (
    CORRELATION_WINDOW_MINUTES,
    MINIMUM_FAMILIES,
    MINIMUM_RULES,
    CorrelatedCase,
    correlate,
)
from .detection import Signal, evaluate, load_rules
from .scenarios import scenario_definition, scenario_events
from .schema import CanonicalEvent

MAX_FRAMES = 600
MAX_RESPONSE_BYTES = 1_048_576
MAX_EVENTS = 5000
MAX_PLAYBACK_EVENTS = 80
_CACHE_LOCK = Lock()
logger = logging.getLogger("aegisgraph.replay")


class ReplayLimitError(ValueError):
    """Safe diagnostics when a projection exceeds its fixed workload contract."""


def _encoded(value: dict | list) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _evidence_id(scope_id: str, event_id: str) -> str:
    return f"EVD-{hashlib.sha256(f'{scope_id}:{event_id}'.encode()).hexdigest()[:16]}"


def _signal_json(signal: Signal) -> dict:
    return {**asdict(signal), "event_ids": list(signal.event_ids)}


def _case_json(case: CorrelatedCase) -> dict:
    return {
        **asdict(case),
        "alert_ids": list(case.alert_ids),
        "event_ids": list(case.event_ids),
        "evidence_ids": [_evidence_id(case.id, event_id) for event_id in case.event_ids],
    }


def _evidence_json(scope_id: str, event: CanonicalEvent) -> dict:
    return {
        "id": _evidence_id(scope_id, event.event_id),
        "incident_id": scope_id,
        "event_id": event.event_id,
        "timestamp": event.timestamp.isoformat(),
        "relevance": "unreviewed",
        "note": "",
        "event": event.model_dump(mode="json"),
    }


def _build(scenario_id: str, rules: list[dict] | None) -> tuple[dict, dict]:
    definition = scenario_definition(scenario_id)
    events = scenario_events(scenario_id)
    if not 1 <= len(events) <= MAX_EVENTS:
        raise ReplayLimitError("Replay exceeds the event workload limit.")
    background_count = 0
    if scenario_id == "atlas-compromise":
        background_count = next(
            index
            for index, event in enumerate(events)
            if event.event_id.startswith("EVT-SCENARIO-")
        )
        if any(
            not event.event_id.startswith("EVT-SCENARIO-") for event in events[background_count:]
        ):
            raise ReplayLimitError("Replay background is not a contiguous initial prefix.")
    playback = events[background_count:]
    if not 1 <= len(playback) <= MAX_PLAYBACK_EVENTS:
        raise ReplayLimitError("Replay exceeds the playback workload limit.")
    selected_rules = copy.deepcopy(load_rules() if rules is None else rules)
    if not 1 <= len(selected_rules) <= 10:
        raise ReplayLimitError("Replay requires a bounded rule set.")
    digest = hashlib.sha256(_encoded(selected_rules).encode()).hexdigest()
    signals = evaluate(events, selected_rules)
    work = {
        "events_processed": len(events),
        "detection_evaluations": 1,
        "correlation_evaluations": 0,
    }
    event_index = {event.event_id: index for index, event in enumerate(events)}
    if len(event_index) != len(events):
        raise ReplayLimitError("Replay requires unique event identifiers.")
    by_trigger: dict[str, list[Signal]] = defaultdict(list)
    for signal in signals:
        if not signal.event_ids or any(
            event_id not in event_index for event_id in signal.event_ids
        ):
            raise ReplayLimitError("Replay signal has invalid evidence references.")
        trigger = signal.event_ids[-1]
        trigger_index = event_index[trigger]
        if trigger_index < background_count:
            raise ReplayLimitError("Replay background contains alerts and cannot be folded.")
        if any(event_index[event_id] > trigger_index for event_id in signal.event_ids):
            raise ReplayLimitError("Replay signal references future telemetry.")
        if signal.timestamp != events[trigger_index].timestamp.isoformat():
            raise ReplayLimitError("Replay signal timestamp does not match its trigger.")
        by_trigger[trigger].append(signal)
    observed = list(events[:background_count])
    emitted: list[Signal] = []
    current_cases: list[CorrelatedCase] = []
    case_snapshots: dict[str, dict] = {}
    frames: list[dict] = []

    def emit(stage: str, timestamp: str, data: dict, **references):
        if len(frames) >= MAX_FRAMES:
            raise ReplayLimitError("Replay exceeds the frame limit.")
        frames.append(
            {
                "seq": len(frames),
                "timestamp": timestamp,
                "stage": stage,
                **references,
                "data": copy.deepcopy(data),
            }
        )

    emit(
        "context_initialized",
        playback[0].timestamp.isoformat(),
        {
            "event_count": background_count,
            "alert_count": 0,
            "incident_count": 0,
            "first_event_at": observed[0].timestamp.isoformat() if observed else None,
            "last_event_at": observed[-1].timestamp.isoformat() if observed else None,
        },
    )
    for event in playback:
        timestamp = event.timestamp.isoformat()
        emit(
            "telemetry",
            timestamp,
            {"source": event.source, "event_type": event.event_type},
            event_id=event.event_id,
        )
        observed.append(event)
        emit(
            "normalized",
            timestamp,
            {"event": event.model_dump(mode="json")},
            event_id=event.event_id,
        )
        for signal in by_trigger.get(event.event_id, ()):
            emit(
                "rule_match",
                timestamp,
                {
                    "rule_id": signal.rule_id,
                    "rule_name": signal.rule_name,
                    "event_ids": list(signal.event_ids),
                    "severity": signal.severity,
                },
                event_id=event.event_id,
                alert_id=signal.id,
            )
            emitted.append(signal)
            emit(
                "alert",
                timestamp,
                _signal_json(signal),
                event_id=event.event_id,
                alert_id=signal.id,
            )
            current_cases = correlate(emitted, observed)
            work["correlation_evaluations"] += 1
            emit(
                "correlation",
                timestamp,
                {
                    "alert_count": len(emitted),
                    "incident_count": len(current_cases),
                    "rule_ids": sorted({item.rule_id for item in emitted}),
                    "rule_families": sorted({item.rule_id.split("-")[0] for item in emitted}),
                    "window_minutes": CORRELATION_WINDOW_MINUTES,
                    "minimum_rules": MINIMUM_RULES,
                    "minimum_families": MINIMUM_FAMILIES,
                },
                event_id=event.event_id,
                alert_id=signal.id,
            )
            for case in current_cases:
                snapshot = _case_json(case)
                previous = case_snapshots.get(case.id)
                if previous != snapshot:
                    emit(
                        "incident",
                        timestamp,
                        {"change": "updated" if previous else "created", "incident": snapshot},
                        event_id=event.event_id,
                        incident_id=case.id,
                    )
                    case_snapshots[case.id] = snapshot
    if len(current_cases) > 1:
        raise ReplayLimitError("Replay requires at most one investigation per scenario.")
    case = current_cases[0] if current_cases else None
    scope_id = case.id if case else f"SCOPE-{scenario_id}"
    evidence_events = (
        set(case.event_ids)
        if case
        else {event.event_id for event in playback}
        | {event_id for signal in emitted for event_id in signal.event_ids}
    )
    if len(evidence_events) > MAX_PLAYBACK_EVENTS:
        raise ReplayLimitError("Replay exceeds the investigation evidence limit.")
    projection = {
        "format_version": "1",
        "provenance": {
            "scenario_id": scenario_id,
            "scenario_version": definition["version"],
            "ruleset_digest": digest,
        },
        "summary": {
            "event_count": len(events),
            "background_event_count": background_count,
            "playback_event_count": len(playback),
            "frame_count": len(frames),
        },
        "initial_state": {"event_count": background_count, "alert_count": 0, "incident_count": 0},
        "frames": frames,
        "final_state": {
            "event_count": len(events),
            "alerts": [_signal_json(signal) for signal in emitted],
            "incidents": [_case_json(case) for case in current_cases],
            "investigation": {
                "id": scope_id,
                "kind": "correlated_incident" if case else "observation_scope",
                "incident_id": case.id if case else None,
                "evidence": [
                    _evidence_json(scope_id, event)
                    for event in events
                    if event.event_id in evidence_events
                ],
            },
        },
    }
    if len(_encoded(projection).encode()) > MAX_RESPONSE_BYTES:
        raise ReplayLimitError("Replay exceeds the response byte limit.")
    return projection, work


def build_projection(scenario_id: str, rules: list[dict] | None = None) -> dict:
    """Pure bounded projection, optionally using a caller-owned rule snapshot."""
    projection, _work = _build(scenario_id, rules)
    return projection


@lru_cache(maxsize=8)
def _serialized_projection(scenario_id: str) -> str:
    start = perf_counter()
    projection, work = _build(scenario_id, None)
    encoded = _encoded(projection)
    logger.info(
        json.dumps(
            {
                "operation": "replay_projection",
                "scenario_id": scenario_id,
                **work,
                "duration_ms": round((perf_counter() - start) * 1000, 2),
            }
        )
    )
    return encoded


def replay_projection(scenario_id: str) -> dict:
    """Baseline replay: fixed eight-entry cache, one cold computation, fresh output."""
    # Include cold corpus generation in the single computation. Unknown IDs fail
    # at scenario_definition in _build; exceptions never occupy an LRU entry.
    with _CACHE_LOCK:
        encoded = _serialized_projection(scenario_id)
    return json.loads(encoded)
