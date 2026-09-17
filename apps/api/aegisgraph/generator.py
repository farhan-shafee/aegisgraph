"""Reproducible, inert telemetry only; no network or process simulation is executed."""

import random
from datetime import UTC, datetime, timedelta

from .adapters import ADAPTERS
from .schema import CanonicalEvent

DEMO_DAY = datetime(2026, 9, 15, tzinfo=UTC)
PRIMARY_USER = "USR-004"


def generate_events(seed: int = 42, normal_count: int = 4000) -> list[CanonicalEvent]:
    rng = random.Random(seed)
    events: list[CanonicalEvent] = []

    def emit(
        timestamp: datetime,
        source: str,
        event_type: str,
        action: str,
        user: int = 4,
        *,
        suspicious: bool = False,
        device: str | None = None,
        role: str = "engineer",
        outcome: str = "success",
        metadata: dict | None = None,
        endpoint: str | None = None,
        resource: str | None = None,
        event_id: str | None = None,
        service: str | None = None,
    ) -> None:
        adapter, type_key = ADAPTERS[source]
        source_ip = "203.0.113.77" if suspicious else f"192.0.2.{user + 10}"
        device_id = device or ("DEV-UNRECOGNIZED-01" if suspicious else f"DEV-{user:03}")
        raw = {
            "id": event_id or f"EVT-{len(events) + 1:06}",
            "time": timestamp,
            type_key: event_type,
            "action": action,
            "outcome": outcome,
            "principal": {
                "user_id": f"USR-{user:03}",
                "username": f"atlas.engineer.{user:02}",
                "role": role,
            },
            "resource": {
                "resource_id": resource,
                "resource_type": "account" if resource else "service",
                "service": service
                or {
                    "identity": "Identity Service",
                    "api_gateway": "API Gateway",
                    "endpoint": "Endpoint telemetry",
                    "atlas": "Account Service",
                }[source],
                "endpoint": endpoint,
            },
            "connection": {
                "source_ip": source_ip,
                "destination_ip": "198.51.100.10",
                "user_agent": "AtlasSynthetic/1.0",
                "location": "synthetic_region_b" if suspicious else "synthetic_region_a",
            },
            "device": {
                "device_id": device_id,
                "trusted": not suspicious,
                "posture": "unknown" if suspicious else "compliant",
            },
            "session": f"SES-{device_id}",
            "metadata": metadata or {},
        }
        events.append(adapter(raw))

    # Every principal has established context before the random workload.
    for user in range(1, 25):
        for offset in range(3):
            emit(
                DEMO_DAY + timedelta(hours=8, minutes=offset),
                "identity",
                "authentication",
                "login",
                user,
                metadata={
                    "source_previously_seen": True,
                    "device_previously_seen": True,
                    "location_previously_seen": True,
                },
            )
    for _ in range(max(0, normal_count - len(events))):
        user = rng.randint(1, 24)
        time = DEMO_DAY + timedelta(hours=8, minutes=10, seconds=rng.randint(0, 20000))
        source = rng.choices(["identity", "api_gateway", "endpoint", "atlas"], [12, 48, 10, 30])[0]
        if source == "identity":
            emit(
                time,
                source,
                "authentication",
                "login",
                user,
                metadata={
                    "source_previously_seen": True,
                    "device_previously_seen": True,
                    "location_previously_seen": True,
                },
            )
        elif source == "api_gateway":
            emit(
                time,
                source,
                "api_request",
                "request",
                user,
                endpoint=rng.choice(
                    ["/v1/positions", "/v1/orders", "/v1/quotes", "/v1/accounts", "/health"]
                ),
                metadata={"method": "GET", "status_code": 200},
            )
        elif source == "endpoint":
            emit(
                time,
                source,
                "device_posture",
                "posture_check",
                user,
                metadata={"security_agent": "healthy"},
            )
        else:
            emit(
                time,
                source,
                "data_access",
                "query",
                user,
                resource=f"ACC-SYN-{rng.randint(1, 99):04}",
                endpoint="/v1/accounts/positions",
                service=rng.choice(["Account Service", "Trading API"]),
                metadata={"records_accessed": rng.randint(1, 90), "baseline_max_records": 90},
            )

    def at(hours: int, minutes: int, seconds: int = 0) -> datetime:
        return DEMO_DAY + timedelta(hours=hours, minutes=minutes, seconds=seconds)

    emit(
        at(13, 57),
        "identity",
        "authentication",
        "login",
        event_id="EVT-SCENARIO-001",
        metadata={
            "source_previously_seen": True,
            "device_previously_seen": True,
            "location_previously_seen": True,
        },
    )
    emit(
        at(14, 2),
        "identity",
        "authentication",
        "login",
        suspicious=True,
        event_id="EVT-SCENARIO-002",
        metadata={
            "source_previously_seen": False,
            "device_previously_seen": False,
            "location_previously_seen": False,
        },
    )
    emit(at(14, 3), "identity", "mfa", "mfa_accept", suspicious=True, event_id="EVT-SCENARIO-003")
    emit(
        at(14, 7),
        "identity",
        "privilege_change",
        "role_assign",
        suspicious=True,
        event_id="EVT-SCENARIO-004",
        metadata={"previous_role": "engineer", "new_role": "platform_admin"},
    )
    for i in range(18):
        emit(
            at(14, 11, i),
            "api_gateway",
            "api_request",
            "request",
            suspicious=True,
            role="platform_admin",
            service="Admin Service",
            event_id=f"EVT-SCENARIO-ENUM-{i + 1:02}",
            endpoint=f"/internal/v1/catalog/{i + 1:02}",
            metadata={
                "method": "GET",
                "status_code": 200,
                "enumeration": i == 17,
                "distinct_endpoints": i + 1,
            },
        )
    emit(
        at(14, 14),
        "atlas",
        "account_access",
        "read_sensitive",
        suspicious=True,
        role="platform_admin",
        resource="ACC-SYN-0042",
        endpoint="/internal/v1/accounts/ACC-SYN-0042/profile",
        event_id="EVT-SCENARIO-006",
        metadata={"sensitive": True},
    )
    emit(
        at(14, 17),
        "atlas",
        "data_access",
        "query",
        suspicious=True,
        role="platform_admin",
        resource="ACC-SYN-BATCH",
        endpoint="/internal/v1/accounts/query",
        event_id="EVT-SCENARIO-007",
        metadata={"records_accessed": 2400, "baseline_max_records": 90},
    )
    emit(
        at(14, 21),
        "identity",
        "authentication",
        "login",
        suspicious=True,
        device="DEV-UNRECOGNIZED-02",
        role="platform_admin",
        event_id="EVT-SCENARIO-008",
        metadata={
            "source_previously_seen": True,
            "device_previously_seen": False,
            "location_previously_seen": True,
        },
    )
    emit(
        at(14, 24),
        "identity",
        "privilege_change",
        "role_revert",
        suspicious=True,
        event_id="EVT-SCENARIO-009",
        metadata={"previous_role": "platform_admin", "new_role": "engineer"},
    )
    return sorted(events, key=lambda event: (event.timestamp, event.event_id))
