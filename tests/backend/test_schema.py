import pytest
from aegisgraph.adapters import ADAPTERS
from aegisgraph.generator import generate_events
from aegisgraph.schema import CanonicalEvent
from pydantic import ValidationError


def test_all_four_adapters_generate_valid_canonical_events():
    events = generate_events(normal_count=100)
    assert {event.source for event in events} == set(ADAPTERS)
    assert all(event.raw["synthetic"] is True for event in events)
    assert events == generate_events(normal_count=100)
    with pytest.raises(ValidationError):
        events[0].action = "tampered"


@pytest.mark.parametrize("field,value", [("source_ip", "invalid"), ("destination_ip", "999.1.1.1")])
def test_network_rejects_invalid_ip(field, value):
    payload = generate_events(normal_count=0)[0].model_dump(mode="json")
    payload["network"][field] = value
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(payload)


def test_rejects_oversized_and_deep_metadata_and_naive_timestamp():
    payload = generate_events(normal_count=0)[0].model_dump(mode="json")
    payload["attributes"] = {"oversized": "x" * 16385}
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(payload)
    nested = {"value": "data"}
    for _ in range(10):
        nested = {"nested": nested}
    payload["attributes"] = nested
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(payload)
    payload["attributes"] = {}
    payload["timestamp"] = "2026-09-15T13:57:00"
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(payload)
