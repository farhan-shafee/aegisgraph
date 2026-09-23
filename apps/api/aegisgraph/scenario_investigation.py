"""Resolve a completed ephemeral scenario under the applicable rule snapshot."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .replay import build_projection, replay_projection
from .rule_specs import baseline_rules
from .rule_workflow import effective_rules


def scenario_projection(db: Session, scenario_id: str, *, public_demo: bool) -> dict:
    try:
        if not public_demo:
            rules = effective_rules(db, public_demo=False)
            if rules != baseline_rules():
                return build_projection(scenario_id, rules)
        return replay_projection(scenario_id)
    except KeyError:
        raise HTTPException(404, "Scenario not found") from None
