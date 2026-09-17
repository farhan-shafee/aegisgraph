"""Detections produce signals; they never create incidents or call a model."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from .config import ROOT
from .schema import CanonicalEvent


def load_rules() -> list[dict]:
    return json.loads((ROOT / "packages/detections/rules.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Signal:
    id: str
    rule_id: str
    rule_name: str
    severity: str
    description: str
    timestamp: str
    user_id: str
    event_ids: tuple[str, ...]


def evaluate(events: list[CanonicalEvent], rules: list[dict] | None = None) -> list[Signal]:
    rules = rules if rules is not None else load_rules()
    history: dict[str, list[CanonicalEvent]] = defaultdict(list)
    novel_auth: dict[str, list[CanonicalEvent]] = defaultdict(list)
    signals: list[Signal] = []
    cooldown: dict[tuple[str, str, str], object] = {}
    novelty_baseline = next((r["threshold"] for r in rules if r["kind"] == "unseen_auth"), 3)
    for event in sorted(events, key=lambda item: (item.timestamp, item.event_id)):
        user = event.actor.user_id
        prior = history[user]
        successful_auth = [
            e for e in prior if e.event_type == "authentication" and e.outcome == "success"
        ]
        is_auth = event.event_type == "authentication" and event.outcome == "success"
        unfamiliar = (
            is_auth
            and len(successful_auth) >= novelty_baseline
            and (
                event.network.source_ip not in {e.network.source_ip for e in successful_auth}
                or event.device.device_id not in {e.device.device_id for e in successful_auth}
            )
        )
        for rule in rules:
            kind = rule["kind"]
            window = timedelta(minutes=rule["window_minutes"])
            recent = [e for e in prior if event.timestamp - e.timestamp <= window]
            auth = [
                e
                for e in novel_auth[user]
                if timedelta(0) < event.timestamp - e.timestamp <= window
                and e.session.session_id == event.session.session_id
            ]
            matching: list[CanonicalEvent] = []
            if (
                kind == "failed_logins"
                and event.event_type == "authentication"
                and event.outcome == "failure"
            ):
                matching = [
                    e for e in recent if e.event_type == "authentication" and e.outcome == "failure"
                ] + [event]
                if len(matching) < rule["threshold"]:
                    matching = []
            elif kind == "unseen_auth" and unfamiliar:
                matching = [successful_auth[-1], event]
            elif (
                kind == "unseen_location" and is_auth and len(successful_auth) >= rule["threshold"]
            ):
                if event.network.location and event.network.location not in {
                    e.network.location for e in successful_auth
                }:
                    matching = [successful_auth[-1], event]
            elif (
                kind == "mfa_after_auth"
                and event.action == "mfa_accept"
                and event.outcome == "success"
                and auth
            ):
                matching = [auth[-1], event]
            elif (
                kind == "privileged_role"
                and event.action == "role_assign"
                and event.outcome == "success"
                and event.attributes.get("new_role") == "platform_admin"
            ):
                matching = [event]
            elif (
                kind == "privilege_after_auth"
                and event.action == "role_assign"
                and event.outcome == "success"
                and event.attributes.get("new_role") == "platform_admin"
                and auth
            ):
                matching = [auth[-1], event]
            elif (
                kind == "enumeration"
                and event.source == "api_gateway"
                and (event.target.endpoint or "").startswith("/internal/")
            ):
                candidates = [
                    e
                    for e in recent
                    if e.source == "api_gateway"
                    and e.session.session_id == event.session.session_id
                    and (e.target.endpoint or "").startswith("/internal/")
                ] + [event]
                if len({e.target.endpoint for e in candidates}) >= rule["threshold"]:
                    matching = candidates
            elif (
                kind == "sensitive_access"
                and event.action == "read_sensitive"
                and event.outcome == "success"
                and event.attributes.get("sensitive") is True
            ):
                matching = [event]
            elif (
                kind == "data_volume"
                and event.event_type == "data_access"
                and event.outcome == "success"
            ):
                records = event.attributes.get("records_accessed")
                if (
                    isinstance(records, int)
                    and not isinstance(records, bool)
                    and records >= rule["threshold"]
                ):
                    matching = [event]
            elif (
                kind == "rapid_reversion"
                and event.action == "role_revert"
                and event.outcome == "success"
            ):
                grants = [
                    e
                    for e in recent
                    if e.action == "role_assign"
                    and e.outcome == "success"
                    and e.attributes.get("new_role") == "platform_admin"
                    and e.timestamp < event.timestamp
                ]
                if grants and event.attributes.get("previous_role") == "platform_admin":
                    matching = [grants[-1], event]
            if matching:
                key = (rule["id"], user, event.session.session_id)
                previous = cooldown.get(key)
                if (
                    kind in {"enumeration", "failed_logins"}
                    and previous
                    and event.timestamp - previous < window
                ):
                    continue
                cooldown[key] = event.timestamp
                ids = tuple(e.event_id for e in matching)
                digest = hashlib.sha256((rule["id"] + "|" + "|".join(ids)).encode()).hexdigest()[
                    :16
                ]
                signals.append(
                    Signal(
                        f"ALT-{digest}",
                        rule["id"],
                        rule["name"],
                        rule["severity"],
                        rule["description"],
                        event.timestamp.isoformat(),
                        user,
                        ids,
                    )
                )
        if unfamiliar:
            novel_auth[user].append(event)
        prior.append(event)
    return signals
