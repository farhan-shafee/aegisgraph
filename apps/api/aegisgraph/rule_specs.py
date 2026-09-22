"""Immutable registered detector snapshots and strictly bounded parameter proposals."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .detection import load_rules

_BASELINE = {rule["id"]: rule for rule in load_rules()}
_ORDER = tuple(_BASELINE)
_CONTROLS = {
    "AUTH-001": {"threshold": (1, 50), "window_minutes": (1, 60)},
    "AUTH-002": {"threshold": (1, 50)},
    "AUTH-003": {"threshold": (1, 50)},
    "MFA-001": {"window_minutes": (1, 30)},
    "IAM-001": {},
    "IAM-002": {"window_minutes": (1, 120)},
    "IAM-003": {"window_minutes": (1, 120)},
    "API-001": {"threshold": (2, 100), "window_minutes": (1, 60)},
    "APP-001": {},
    "APP-002": {"threshold": (100, 10000)},
}


def _description(rule_id: str, threshold: int, window: int) -> str:
    original = _BASELINE[rule_id]
    if threshold == original["threshold"] and window == original["window_minutes"]:
        return original["description"]
    descriptions = {
        "AUTH-001": f"At least {threshold} failed logins for a user in {window} minutes.",
        "AUTH-002": f"Successful login uses an IP or device absent from at least {threshold} prior successful logins.",
        "AUTH-003": f"Successful login uses a synthetic location absent from at least {threshold} prior successful logins. Location is a simulator label, not real IP geolocation.",
        "MFA-001": f"MFA acceptance within {window} minutes after an unfamiliar successful authentication on the same session.",
        "IAM-002": f"A privileged role is granted within {window} minutes of unfamiliar successful authentication for the same user/session.",
        "API-001": f"At least {threshold} distinct internal endpoints requested by one user/session within {window} minutes. Alert emits once per window.",
        "APP-002": f"A successful query accesses at least {threshold:,} records. Original Atlas background queries access no more than 90; benign automation can exceed this.",
        "IAM-003": f"A granted platform administrator role is reverted for the same user within {window} minutes.",
    }
    return descriptions.get(rule_id, original["description"])


class RuleDefinition(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )

    id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    severity: Literal["low", "medium", "high", "critical"]
    kind: Literal[
        "failed_logins",
        "unseen_auth",
        "unseen_location",
        "mfa_after_auth",
        "privileged_role",
        "privilege_after_auth",
        "enumeration",
        "sensitive_access",
        "data_volume",
        "rapid_reversion",
    ]
    window_minutes: int = Field(ge=0, le=120)
    threshold: int = Field(ge=1, le=10000)
    description: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def registered_parameters(self):
        original = _BASELINE.get(self.id)
        if original is None:
            raise ValueError("Rule identifier is not registered")
        if any(getattr(self, name) != original[name] for name in ("name", "severity", "kind")):
            raise ValueError("Rule identity, kind, name, and severity are fixed")
        for parameter in ("threshold", "window_minutes"):
            value = getattr(self, parameter)
            bounds = _CONTROLS[self.id].get(parameter)
            if bounds is None:
                if value != original[parameter]:
                    raise ValueError("This rule parameter is not adjustable")
            elif not bounds[0] <= value <= bounds[1]:
                raise ValueError("Rule parameter is outside its allowed range")
        if self.description != _description(self.id, self.threshold, self.window_minutes):
            raise ValueError("Rule description does not match its effective parameters")
        return self


class RuleSet(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )

    rules: tuple[RuleDefinition, ...] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def complete_registered_order(self):
        if tuple(rule.id for rule in self.rules) != _ORDER:
            raise ValueError(
                "A rule snapshot must contain each registered rule once in canonical order"
            )
        return self


class RuleParameterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    threshold: int | None = Field(default=None, ge=1, le=10000)
    window_minutes: int | None = Field(default=None, ge=1, le=120)


def validate_rules(rules: list[dict] | RuleSet) -> RuleSet:
    if isinstance(rules, RuleSet):
        return RuleSet.model_validate(rules)
    if not isinstance(rules, list) or len(rules) != 10:
        raise ValueError("A rule snapshot requires ten registered definitions")
    return RuleSet(rules=tuple(RuleDefinition.model_validate(rule) for rule in rules))


def baseline_rules() -> list[dict]:
    return [rule.model_dump() for rule in validate_rules(load_rules()).rules]


def rule_parameters(rule_id: str) -> list[dict]:
    original = _BASELINE[rule_id]
    return [
        {
            "name": name,
            "label": "Window (minutes)" if name == "window_minutes" else "Threshold",
            "minimum": bounds[0],
            "maximum": bounds[1],
            "step": 1,
            "default": original[name],
        }
        for name, bounds in _CONTROLS[rule_id].items()
    ]


def propose_rules(
    current_rules: list[dict] | RuleSet, rule_id: str, parameters: dict
) -> list[dict]:
    current = validate_rules(current_rules)
    _BASELINE[rule_id]  # Unknown rule identifiers never become filenames or expressions.
    patch = RuleParameterPatch.model_validate(parameters).model_dump(exclude_unset=True)
    if not patch or any(value is None for value in patch.values()):
        raise ValueError("Provide at least one non-null effective parameter")
    if not set(patch).issubset(_CONTROLS[rule_id]):
        raise ValueError("Only effective parameters may be changed")
    proposed = [rule.model_dump() for rule in current.rules]
    target = next(rule for rule in proposed if rule["id"] == rule_id)
    if all(target[name] == value for name, value in patch.items()):
        raise ValueError("A proposal must change at least one parameter")
    target.update(patch)
    target["description"] = _description(rule_id, target["threshold"], target["window_minutes"])
    return [rule.model_dump() for rule in validate_rules(proposed).rules]


def ruleset_digest(rules: list[dict] | RuleSet) -> str:
    snapshot = [rule.model_dump() for rule in validate_rules(rules).rules]
    canonical = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
