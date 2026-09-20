"""Bounded, read-only descriptions of repository-owned synthetic scenarios."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class ScenarioDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,59}$")
    version: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    classification: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=2000)
    theme: str = Field(min_length=1, max_length=2000)
    event_count: int = Field(ge=1, le=5000)
    canonical_incident_id: str | None = Field(default=None, max_length=80)


class ScenarioCatalog(BaseModel):
    items: list[ScenarioDescription] = Field(max_length=10)


@router.get("", response_model=ScenarioCatalog)
def list_scenarios():
    from .scenarios import catalog

    return {"items": catalog()}


@router.get("/{scenario_id}", response_model=ScenarioDescription)
def get_scenario(scenario_id: str):
    from .scenarios import scenario_definition

    try:
        return scenario_definition(scenario_id)
    except KeyError:
        raise HTTPException(404, "Scenario not found") from None
