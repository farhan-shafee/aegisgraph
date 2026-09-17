"""Four explicit adapters. Raw data is allowlisted synthetic metadata, never arbitrary uploads."""

from typing import Any

from .schema import CanonicalEvent


def _normalize(raw: dict[str, Any], source: str, type_key: str) -> CanonicalEvent:
    return CanonicalEvent.model_validate(
        {
            "event_id": raw["id"],
            "timestamp": raw["time"],
            "source": source,
            "event_type": raw[type_key],
            "action": raw["action"],
            "outcome": raw["outcome"],
            "actor": raw["principal"],
            "target": raw["resource"],
            "network": raw["connection"],
            "device": raw["device"],
            "session": {"session_id": raw["session"]},
            "attributes": raw.get("metadata", {}),
            "raw": {"synthetic": True, "adapter": source, "source_event_id": raw["id"]},
        }
    )


def normalize_identity(raw: dict[str, Any]) -> CanonicalEvent:
    return _normalize(raw, "identity", "identity_type")


def normalize_gateway(raw: dict[str, Any]) -> CanonicalEvent:
    return _normalize(raw, "api_gateway", "request_type")


def normalize_endpoint(raw: dict[str, Any]) -> CanonicalEvent:
    return _normalize(raw, "endpoint", "signal_type")


def normalize_atlas(raw: dict[str, Any]) -> CanonicalEvent:
    return _normalize(raw, "atlas", "application_type")


ADAPTERS = {
    "identity": (normalize_identity, "identity_type"),
    "api_gateway": (normalize_gateway, "request_type"),
    "endpoint": (normalize_endpoint, "signal_type"),
    "atlas": (normalize_atlas, "application_type"),
}
