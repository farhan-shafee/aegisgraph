"""Deterministic correlation joins multiple rule families by principal and time."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from .detection import Signal
from .schema import CanonicalEvent


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
    cases = []
    users = sorted({signal.user_id for signal in signals})
    for user in users:
        user_signals = sorted(
            (s for s in signals if s.user_id == user),
            key=lambda s: datetime.fromisoformat(s.timestamp),
        )
        clusters: list[list[Signal]] = []
        for signal in user_signals:
            if not clusters or datetime.fromisoformat(signal.timestamp) - datetime.fromisoformat(
                clusters[-1][0].timestamp
            ) > timedelta(minutes=30):
                clusters.append([])
            clusters[-1].append(signal)
        for cluster in clusters:
            families = {s.rule_id.split("-")[0] for s in cluster}
            # A lone signal stays an alert. Incidents require independent identity/access signals.
            if len(families) < 2 or len({s.rule_id for s in cluster}) < 3:
                continue
            start = datetime.fromisoformat(cluster[0].timestamp) - timedelta(minutes=5)
            end = datetime.fromisoformat(cluster[-1].timestamp)
            selected = [
                e for e in events if e.actor.user_id == user and start <= e.timestamp <= end
            ]
            event_ids = set(e.event_id for e in selected)
            event_ids.update(event_id for signal in cluster for event_id in signal.event_ids)
            severity = "high" if "APP" in families and "IAM" in families else "medium"
            digest = hashlib.sha256((user + cluster[0].id).encode()).hexdigest()[:12]
            rules = {s.rule_id for s in cluster}
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
                    f"INC-{digest}",
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
    return cases
