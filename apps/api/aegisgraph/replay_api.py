"""A finite replay is a read, never a public session or write operation."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .scenario_investigation import scenario_projection

router = APIRouter(prefix="/api/replays", tags=["replay"])


class ReplayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReplayProvenance(ReplayModel):
    scenario_id: str
    scenario_version: str
    ruleset_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReplaySummary(ReplayModel):
    event_count: int = Field(ge=0, le=5000)
    background_event_count: int = Field(ge=0, le=5000)
    playback_event_count: int = Field(ge=0, le=80)
    frame_count: int = Field(ge=0, le=600)


class ReplayInitialState(ReplayModel):
    event_count: int = Field(ge=0, le=5000)
    alert_count: Literal[0]
    incident_count: Literal[0]


class ReplayFrame(ReplayModel):
    seq: int = Field(ge=0, le=600)
    timestamp: str
    stage: Literal[
        "context_initialized",
        "telemetry",
        "normalized",
        "rule_match",
        "alert",
        "correlation",
        "incident",
    ]
    event_id: str | None = None
    alert_id: str | None = None
    incident_id: str | None = None
    data: dict[str, Any]


class ReplayInvestigation(ReplayModel):
    id: str
    kind: Literal["correlated_incident", "observation_scope"]
    incident_id: str | None
    evidence: list[dict[str, Any]] = Field(max_length=80)


class ReplayFinalState(ReplayModel):
    event_count: int = Field(ge=0, le=5000)
    alerts: list[dict[str, Any]] = Field(max_length=100)
    incidents: list[dict[str, Any]] = Field(max_length=10)
    investigation: ReplayInvestigation


class ReplayProjection(ReplayModel):
    format_version: Literal["1"]
    provenance: ReplayProvenance
    summary: ReplaySummary
    initial_state: ReplayInitialState
    frames: list[ReplayFrame] = Field(max_length=600)
    final_state: ReplayFinalState


@router.get("/{scenario_id}", response_model=ReplayProjection, response_model_exclude_unset=True)
def get_replay(
    scenario_id: Annotated[str, Path(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9-]*$")],
    request: Request,
    db: Session = Depends(get_db),
):
    if request.query_params:
        raise HTTPException(422, "Replay query parameters are not supported")
    return scenario_projection(db, scenario_id, public_demo=config.settings.public_demo)
