"""Versioned inert telemetry fixtures; evaluation answer keys live in a separate module.

The corpus never writes to a database or executes simulated activity. Cached values
are serialized strings: callers receive fresh canonical events, including metadata.
"""

from dataclasses import asdict, dataclass
from datetime import timedelta
from functools import lru_cache

from .adapters import ADAPTERS
from .generator import DEMO_DAY, generate_events
from .schema import CanonicalEvent


@dataclass(frozen=True)
class _Definition:
    id: str
    title: str
    classification: str
    purpose: str
    theme: str
    canonical_incident_id: str | None = None
    version: str = "1"


_DEFINITIONS = {
    item.id: item
    for item in (
        _Definition(
            "atlas-compromise",
            "Atlas account investigation",
            "suspicious",
            "Trace unfamiliar account activity from authentication through privileged resource access.",
            "Account access and privilege changes",
            "INC-fe8fa4b9508c",
        ),
        _Definition(
            "auth-pressure",
            "Authentication pressure",
            "suspicious",
            "Inspect repeated authentication failures followed by unfamiliar access and MFA acceptance.",
            "Authentication sequence and missing identity proof",
        ),
        _Definition(
            "service-access",
            "Service principal access",
            "suspicious",
            "Review a service principal's resource requests and account-data access outside its recorded job scope.",
            "Service credential scope and access observations",
        ),
        _Definition(
            "sensitive-enumeration",
            "Sensitive resource exploration",
            "ambiguous",
            "Inspect a compact internal endpoint sequence and a sensitive read without assuming account compromise.",
            "Enumeration and correlation sufficiency",
        ),
        _Definition(
            "approved-admin",
            "Approved temporary administration",
            "benign",
            "Compare a recorded maintenance approval with a temporary administrator grant and reversion.",
            "Security signals with benign change context",
        ),
        _Definition(
            "bulk-automation",
            "Scheduled bulk reconciliation",
            "benign",
            "Inspect account-data volume alongside a recorded reconciliation job and its scope.",
            "Volume alerts and automation context",
        ),
        _Definition(
            "isolated-anomaly",
            "Isolated unfamiliar sign-in",
            "insufficient_evidence",
            "Inspect one changed source and device with no follow-on privileged or resource activity.",
            "Anomaly versus established compromise",
        ),
        _Definition(
            "mixed-context",
            "Conflicting account context",
            "mixed",
            "Compare an unfamiliar access sequence with a documented role approval and a known-device observation.",
            "Competing explanations and unresolved session identity",
        ),
    )
}


def _event(
    scenario_id: str,
    suffix: str,
    minute: float,
    *,
    source: str = "identity",
    event_type: str = "authentication",
    action: str = "login",
    unfamiliar: bool = False,
    changed_location: bool = True,
    outcome: str = "success",
    role: str | None = None,
    metadata: dict | None = None,
    endpoint: str | None = None,
    resource: str | None = None,
) -> CanonicalEvent:
    adapter, type_key = ADAPTERS[source]
    service_actor = scenario_id in {"service-access", "bulk-automation"}
    device = f"DEV-{scenario_id}-{'new' if unfamiliar else 'known'}"
    attributes = dict(metadata or {})
    if event_type == "authentication" and outcome == "success":
        attributes.update(
            source_previously_seen=not unfamiliar,
            device_previously_seen=not unfamiliar,
            location_previously_seen=not (unfamiliar and changed_location),
        )
    return adapter(
        {
            "id": f"EVT-{scenario_id}-{suffix}",
            "time": DEMO_DAY + timedelta(hours=14, minutes=minute),
            type_key: event_type,
            "action": action,
            "outcome": outcome,
            "principal": {
                "user_id": f"USR-{scenario_id}",
                "username": f"atlas.{scenario_id}.synthetic",
                "role": role or ("service_account" if service_actor else "engineer"),
            },
            "resource": {
                "resource_id": resource,
                "resource_type": "account" if resource else "service",
                "service": {
                    "identity": "Identity Service",
                    "api_gateway": "API Gateway",
                    "endpoint": "Endpoint telemetry",
                    "atlas": "Account Service",
                }[source],
                "endpoint": endpoint,
            },
            "connection": {
                "source_ip": "203.0.113.70" if unfamiliar else "192.0.2.70",
                "destination_ip": "198.51.100.10",
                "user_agent": "AtlasSynthetic/2.0",
                "location": "synthetic_region_b"
                if unfamiliar and changed_location
                else "synthetic_region_a",
            },
            "device": {
                "device_id": device,
                "trusted": not unfamiliar,
                "posture": "unknown" if unfamiliar else "compliant",
            },
            "session": f"SES-{scenario_id}-{'new' if unfamiliar else 'known'}",
            "metadata": attributes,
        }
    )


def _baseline(scenario_id: str) -> list[CanonicalEvent]:
    return [_event(scenario_id, f"baseline-{i + 1}", -30 + i) for i in range(3)]


def _enumeration(scenario_id: str, count: int, *, start: float = 1) -> list[CanonicalEvent]:
    return [
        _event(
            scenario_id,
            f"request-{i + 1:02}",
            start + i / 60,
            source="api_gateway",
            event_type="api_request",
            action="request",
            endpoint=f"/internal/v1/{scenario_id}/catalog/{i + 1:02}",
            metadata={"method": "GET", "status_code": 200},
        )
        for i in range(count)
    ]


def _role(scenario_id: str, minute: float, *, revert: bool = False, unfamiliar: bool = False):
    return _event(
        scenario_id,
        "role-revert" if revert else "role-grant",
        minute,
        event_type="privilege_change",
        action="role_revert" if revert else "role_assign",
        unfamiliar=unfamiliar,
        metadata={
            "previous_role": "platform_admin" if revert else "engineer",
            "new_role": "engineer" if revert else "platform_admin",
        },
    )


def _sensitive(scenario_id: str, minute: float, *, unfamiliar: bool = False):
    return _event(
        scenario_id,
        "sensitive-read",
        minute,
        source="atlas",
        event_type="account_access",
        action="read_sensitive",
        unfamiliar=unfamiliar,
        resource=f"ACC-SYN-{scenario_id}",
        endpoint=f"/internal/v1/accounts/{scenario_id}/profile",
        metadata={"sensitive": True},
    )


def _small_scenario(scenario_id: str) -> list[CanonicalEvent]:
    events = _baseline(scenario_id)
    if scenario_id == "auth-pressure":
        events += [
            _event(scenario_id, f"failure-{i + 1}", i / 2, unfamiliar=True, outcome="failure")
            for i in range(5)
        ]
        events += [
            _event(scenario_id, "unfamiliar-login", 3, unfamiliar=True),
            _event(
                scenario_id,
                "mfa-accepted",
                4,
                event_type="mfa",
                action="mfa_accept",
                unfamiliar=True,
            ),
        ]
    elif scenario_id == "service-access":
        events.append(
            _event(
                scenario_id,
                "job-scope",
                0,
                source="atlas",
                event_type="automation_context",
                action="job_scope_recorded",
                metadata={"job_id": "JOB-SYN-INVENTORY", "approved_scope": "public_catalog_only"},
            )
        )
        events += _enumeration(scenario_id, 13)
        events += [
            _sensitive(scenario_id, 3),
            _event(
                scenario_id,
                "bulk-read",
                4,
                source="atlas",
                event_type="data_access",
                action="query",
                resource="ACC-SYN-SERVICE-BATCH",
                endpoint="/internal/v1/accounts/query",
                metadata={
                    "records_accessed": 1800,
                    "job_id": "JOB-SYN-INVENTORY",
                    "baseline_max_records": 90,
                },
            ),
        ]
    elif scenario_id == "sensitive-enumeration":
        events += _enumeration(scenario_id, 12)
        events.append(_sensitive(scenario_id, 4))
    elif scenario_id == "approved-admin":
        events += [
            _event(
                scenario_id,
                "change-approval",
                0,
                event_type="change_context",
                action="change_approved",
                metadata={
                    "change_id": "CHG-SYN-MAINTENANCE",
                    "approved_role": "platform_admin",
                    "purpose": "Scheduled configuration review",
                    "approved_minutes": 15,
                },
            ),
            _role(scenario_id, 1),
            _event(
                scenario_id,
                "maintenance-read",
                3,
                source="api_gateway",
                event_type="api_request",
                action="request",
                role="platform_admin",
                endpoint="/internal/v1/configuration",
                metadata={"method": "GET", "status_code": 200, "change_id": "CHG-SYN-MAINTENANCE"},
            ),
            _role(scenario_id, 10, revert=True),
        ]
    elif scenario_id == "bulk-automation":
        events += [
            _event(
                scenario_id,
                "job-scope",
                0,
                source="atlas",
                event_type="automation_context",
                action="job_scope_recorded",
                metadata={
                    "job_id": "JOB-SYN-RECONCILE",
                    "purpose": "Scheduled account reconciliation",
                    "approved_record_limit": 1500,
                    "destination": "internal_reconciliation_store",
                },
            ),
            _event(
                scenario_id,
                "bulk-read",
                1,
                source="atlas",
                event_type="data_access",
                action="query",
                resource="ACC-SYN-RECONCILE-BATCH",
                endpoint="/v1/accounts/reconciliation",
                metadata={
                    "records_accessed": 1200,
                    "job_id": "JOB-SYN-RECONCILE",
                    "baseline_max_records": 90,
                },
            ),
            _event(
                scenario_id,
                "job-complete",
                2,
                source="atlas",
                event_type="automation_context",
                action="job_completed",
                metadata={"job_id": "JOB-SYN-RECONCILE", "records_processed": 1200},
            ),
        ]
    elif scenario_id == "isolated-anomaly":
        events.append(
            _event(scenario_id, "unfamiliar-login", 0, unfamiliar=True, changed_location=False)
        )
    elif scenario_id == "mixed-context":
        events += [
            _event(
                scenario_id,
                "change-approval",
                -1,
                event_type="change_context",
                action="change_approved",
                metadata={
                    "change_id": "CHG-SYN-MIXED",
                    "approved_role": "platform_admin",
                    "purpose": "Approved account-support maintenance",
                    "approved_session": f"SES-{scenario_id}-known",
                },
            ),
            _event(scenario_id, "unfamiliar-login", 0, unfamiliar=True),
            _event(
                scenario_id,
                "mfa-accepted",
                1,
                event_type="mfa",
                action="mfa_accept",
                unfamiliar=True,
            ),
            _role(scenario_id, 2, unfamiliar=True),
            _sensitive(scenario_id, 4, unfamiliar=True),
            _event(
                scenario_id,
                "known-device-posture",
                5,
                source="endpoint",
                event_type="device_posture",
                action="posture_check",
                metadata={
                    "security_agent": "healthy",
                    "observation": "Known device still reports; this does not identify the actor on the other session.",
                },
            ),
            _role(scenario_id, 8, revert=True, unfamiliar=True),
        ]
    return sorted(events, key=lambda item: (item.timestamp, item.event_id))


@lru_cache(maxsize=8)
def _serialized_events(scenario_id: str) -> tuple[str, ...]:
    _DEFINITIONS[scenario_id]  # Validate the allowlist before generation or caching.
    events = (
        generate_events(seed=42)
        if scenario_id == "atlas-compromise"
        else _small_scenario(scenario_id)
    )
    return tuple(event.model_dump_json() for event in events)


def scenario_events(scenario_id: str) -> list[CanonicalEvent]:
    """Return fresh ordered telemetry; no shallow mutable model is shared with callers."""
    return [CanonicalEvent.model_validate_json(item) for item in _serialized_events(scenario_id)]


def scenario_definition(scenario_id: str) -> dict:
    """Analyst-facing metadata only: no labels, expected matches, or answer-key claims."""
    definition = _DEFINITIONS[scenario_id]
    return {**asdict(definition), "event_count": len(_serialized_events(scenario_id))}


def catalog() -> list[dict]:
    return [scenario_definition(scenario_id) for scenario_id in _DEFINITIONS]
