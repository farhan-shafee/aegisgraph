import ipaddress
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["new", "investigating", "contained", "resolved"]


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Actor(ImmutableModel):
    user_id: str = Field(max_length=100)
    username: str = Field(max_length=100)
    role: str = Field(max_length=100)


class Target(ImmutableModel):
    resource_id: str | None = Field(default=None, max_length=200)
    resource_type: str = Field(max_length=100)
    service: str = Field(max_length=100)
    endpoint: str | None = Field(default=None, max_length=500)


class Network(ImmutableModel):
    source_ip: str = Field(max_length=45)
    destination_ip: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=100)

    @field_validator("source_ip", "destination_ip")
    @classmethod
    def valid_ip(cls, value: str | None) -> str | None:
        if value is not None:
            ipaddress.ip_address(value)
        return value


class Device(ImmutableModel):
    device_id: str = Field(min_length=1, max_length=100)
    trusted: bool
    posture: str = Field(max_length=100)


class Session(ImmutableModel):
    session_id: str = Field(min_length=1, max_length=100)


class CanonicalEvent(ImmutableModel):
    event_id: str = Field(pattern=r"^EVT-[A-Za-z0-9-]+$", max_length=80)
    timestamp: datetime
    source: Literal["identity", "api_gateway", "endpoint", "atlas"]
    event_type: str = Field(max_length=100)
    action: str = Field(max_length=100)
    outcome: Literal["success", "failure", "unknown"]
    actor: Actor
    target: Target
    network: Network
    device: Device
    session: Session
    attributes: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] | None = None

    @field_validator("attributes", "raw")
    @classmethod
    def bounded_json(cls, value):
        def depth(item, level=0):
            if level > 8:
                raise ValueError("metadata nesting exceeds eight levels")
            if isinstance(item, dict):
                for child in item.values():
                    depth(child, level + 1)
            elif isinstance(item, list):
                for child in item:
                    depth(child, level + 1)

        depth(value)
        if len(json.dumps(value, allow_nan=False).encode("utf-8")) > 16384:
            raise ValueError("metadata exceeds 16 KiB")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("event timestamps must include a timezone")
        return value


class IncidentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: IncidentStatus | None = None
    severity: Severity | None = None
    owner: str | None = Field(default=None, max_length=100)


class EvidencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relevance: Literal["unreviewed", "relevant", "benign"] | None = None
    note: str | None = Field(default=None, max_length=2000)


class FindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(min_length=1, max_length=5000)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    ai_assisted: bool = False
    approved: bool = False


class FindingApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=5000)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
