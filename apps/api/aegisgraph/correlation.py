"""Deterministic correlation joins multiple rule families by principal and time."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .detection import Signal
from .schema import CanonicalEvent

CORRELATION_WINDOW_MINUTES = 30
MINIMUM_RULES = 3
MINIMUM_FAMILIES = 2
CORRELATION_POLICY_VERSION = "principal-window-v1"


@dataclass(frozen=True)
class CorrelatedCase:
    id: str
    title: str
    severity: str
    summary: str
    alert_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    user_id: str


def correlate(signals: list[Signal], events: list[CanonicalEvent]) -> list[CorrelatedCase]:
    cases, _decisions = correlate_with_decisions(signals, events)
    return cases


def correlate_with_decisions(
    signals: list[Signal], events: list[CanonicalEvent]
) -> tuple[list[CorrelatedCase], list[dict]]:
    """Build cases and receipts from one principal/anchored-window qualification.

    Receipts describe observed alert clusters, including those below the minimums.
    Approval, session, device and IP context never suppresses or joins a cluster.
    """
    cases = []
    decisions = []
    users = sorted({signal.user_id for signal in signals})
    for user in users:
        user_signals = sorted(
            (s for s in signals if s.user_id == user),
            key=lambda s: (datetime.fromisoformat(s.timestamp), s.rule_id, s.id),
        )
        clusters: list[list[Signal]] = []
        for signal in user_signals:
            if not clusters or datetime.fromisoformat(signal.timestamp) - datetime.fromisoformat(
                clusters[-1][0].timestamp
            ) > timedelta(minutes=CORRELATION_WINDOW_MINUTES):
                clusters.append([])
            clusters[-1].append(signal)
        for cluster in clusters:
            families = {s.rule_id.split("-")[0] for s in cluster}
            rules = {s.rule_id for s in cluster}
            first = datetime.fromisoformat(cluster[0].timestamp).astimezone(UTC)
            last = datetime.fromisoformat(cluster[-1].timestamp).astimezone(UTC)
            unmet_conditions = []
            if len(rules) < MINIMUM_RULES:
                unmet_conditions.append("distinct_rules")
            if len(families) < MINIMUM_FAMILIES:
                unmet_conditions.append("rule_families")
            incident_id = None
            if not unmet_conditions:
                digest = hashlib.sha256((user + cluster[0].id).encode()).hexdigest()[:12]
                incident_id = f"INC-{digest}"
            decisions.append(
                {
                    "policy_version": CORRELATION_POLICY_VERSION,
                    "principal_id": user,
                    "alert_ids": [signal.id for signal in cluster],
                    "rule_ids": sorted(rules),
                    "rule_families": sorted(families),
                    "first_alert_at": first.isoformat(),
                    "last_alert_at": last.isoformat(),
                    "window_end_at": (
                        first + timedelta(minutes=CORRELATION_WINDOW_MINUTES)
                    ).isoformat(),
                    "span_minutes": round((last - first).total_seconds() / 60, 2),
                    "window_minutes": CORRELATION_WINDOW_MINUTES,
                    "minimum_rules": MINIMUM_RULES,
                    "minimum_families": MINIMUM_FAMILIES,
                    "unmet_conditions": unmet_conditions,
                    "incident_id": incident_id,
                }
            )
            # A lone signal stays an alert; the same decision gates case creation.
            if incident_id is None:
                continue
            start = first - timedelta(minutes=5)
            end = last
            selected = [
                e for e in events if e.actor.user_id == user and start <= e.timestamp <= end
            ]
            event_ids = set(e.event_id for e in selected)
            event_ids.update(event_id for signal in cluster for event_id in signal.event_ids)
            severity = "high" if "APP" in families and "IAM" in families else "medium"
            flagship = {"AUTH-002", "IAM-001", "APP-001"}.issubset(rules)
            summary = (
                (
                    "Unfamiliar authentication, privileged access, and account-resource activity share one principal within a thirty-minute window. "
                    if flagship
                    else "Multiple detection families share one principal within a thirty-minute window: "
                    + ", ".join(sorted(families))
                    + ". "
                )
                + "Session, device and IP relationships provide context; telemetry does not establish malware or external exfiltration."
            )
            cases.append(
                CorrelatedCase(
                    incident_id,
                    "Suspected compromise of Atlas engineer account"
                    if flagship
                    else "Correlated security signals for Atlas principal",
                    severity,
                    summary,
                    tuple(s.id for s in cluster),
                    tuple(sorted(event_ids)),
                    user,
                )
            )
    return cases, decisions


def explain_correlation(alerts: list[dict]) -> dict:
    principals = sorted({item["user_id"] for item in alerts})
    rule_ids = sorted({item["rule_id"] for item in alerts})
    families = sorted({rule.split("-")[0] for rule in rule_ids})
    timestamps = sorted(datetime.fromisoformat(item["timestamp"]) for item in alerts)
    span = round((timestamps[-1] - timestamps[0]).total_seconds() / 60, 2) if timestamps else 0
    meets_thresholds = len(rule_ids) >= MINIMUM_RULES and len(families) >= MINIMUM_FAMILIES
    explanation = [
        f"{len(alerts)} alerts reference {len(principals)} principal(s): {', '.join(principals) or 'none'}.",
        f"{len(rule_ids)} distinct rules across {len(families)} families {'meet' if meets_thresholds else 'do not meet'} the minimum of {MINIMUM_RULES} rules and {MINIMUM_FAMILIES} families.",
        f"First-to-last alert span is {span:g} minutes; the clustering window is {CORRELATION_WINDOW_MINUTES} minutes, anchored at the first alert.",
        "Principal and event time are grouping predicates. Device, session, and IP relationships provide investigation context; they do not independently join cases.",
    ]
    return {
        "principal_ids": principals,
        "alert_count": len(alerts),
        "distinct_rule_count": len(rule_ids),
        "rule_ids": rule_ids,
        "rule_families": families,
        "first_alert_at": timestamps[0].isoformat() if timestamps else None,
        "last_alert_at": timestamps[-1].isoformat() if timestamps else None,
        "span_minutes": span,
        "window_minutes": CORRELATION_WINDOW_MINUTES,
        "minimum_rules": MINIMUM_RULES,
        "minimum_families": MINIMUM_FAMILIES,
        "grouping_keys": ["principal", "event_time"],
        "context_only": ["device", "session", "ip"],
        "explanation": explanation,
    }
