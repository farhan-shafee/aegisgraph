"""Deterministic, scoped propositions and bounded counterevidence.

Recorded approvals and job scopes can explain a narrowly stated observation.
They cannot establish who controlled an account, authenticate their own origin,
or prove that compromise did not occur. No provider or ground-truth label is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from itertools import combinations

from pydantic import ValidationError

from .analyst import (
    IDENTIFIER,
    MAX_CONTEXT_BYTES,
    MAX_EVIDENCE,
    AnalysisInputError,
    build_context,
    supported_claims,
)
from .schema import CanonicalEvent

DERIVATION_VERSION = "1"
MAX_INPUT_BYTES = 1_048_576
MAX_LEDGER_BYTES = 32_000
_ROLES = {"admin", "administrator", "platform_admin", "platform-admin", "superuser"}
_TITLES = {
    "account_compromise": "Account activity reflects unauthorized control",
    "suspicious_privilege_sequence": "Unfamiliar authentication preceded privilege assignment and sensitive access",
    "unapproved_privilege_change": "Privileged-role assignment was outside its recorded change approval",
    "unexplained_bulk_access": "Bulk access exceeded its recorded automation allowance",
    "malware_execution": "Evidence needed to assess malware execution",
}
_GUIDANCE = {
    "account_owner_verification": "Verify the observed activity with the account owner through an independent channel; recorded telemetry alone does not identify the operator.",
    "identity_session_history": "Collect identity-provider session history and independently verify the session's authorization and controller.",
    "additional_telemetry": "Collect scoped authentication, privileged-role assignment, and sensitive-access telemetry to evaluate their ordering for the same principal within 30 minutes.",
    "change_approval": "Obtain the recorded change approval bound to the same principal, authorized session, assigned role, and approved time interval; absence of an approval is not proof of unauthorized activity.",
    "automation_job_scope": "Obtain the recorded automation scope and numeric allowance bound to the same principal, session, and job; account for cumulative query volume within 30 minutes.",
    "endpoint_forensics": "Collect endpoint process, execution, and forensic evidence before assessing malware execution or a malware family.",
}
_GAPS = {
    "account_compromise": ("account_owner_verification", "identity_session_history"),
    "suspicious_privilege_sequence": ("additional_telemetry",),
    "unapproved_privilege_change": ("change_approval",),
    "unexplained_bulk_access": ("automation_job_scope",),
    "malware_execution": ("endpoint_forensics",),
}


class HypothesisInputError(AnalysisInputError):
    """A safe fixed diagnostic; never includes source telemetry or caller text."""


def _encoded(value) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise HypothesisInputError("invalid_hypothesis_input") from exc


def _identifier(value) -> bool:
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def _timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise HypothesisInputError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise HypothesisInputError("invalid_timestamp") from exc


def _integer(value, minimum=1, maximum=1_000_000_000):
    return value if type(value) is int and minimum <= value <= maximum else None


def _context_fields(event: dict) -> dict:
    """Only narrow typed fields affect local derivation; this is not a provider input."""
    attributes = event["attributes"]
    role = attributes.get("role", attributes.get("new_role", attributes.get("assigned_role")))
    approved_role = attributes.get("approved_role")
    approved_session = attributes.get("approved_session")
    return {
        "source": event["source"],
        "context_type": event["event_type"]
        if event["event_type"] in {"change_context", "automation_context"}
        else None,
        "context_action": event["action"]
        if event["action"] in {"change_approved", "job_scope_recorded"}
        else None,
        "role": role if isinstance(role, str) and role in _ROLES else None,
        "approved_role": approved_role
        if isinstance(approved_role, str) and approved_role in _ROLES
        else None,
        "approved_minutes": _integer(attributes.get("approved_minutes"), maximum=30),
        "approved_session": approved_session if _identifier(approved_session) else None,
        "approved_session_present": "approved_session" in attributes,
        "change_id": attributes.get("change_id")
        if _identifier(attributes.get("change_id"))
        else None,
        "job_id": attributes.get("job_id") if _identifier(attributes.get("job_id")) else None,
        "approved_record_limit": _integer(attributes.get("approved_record_limit")),
        "approved_scope": "public_catalog_only"
        if attributes.get("approved_scope") == "public_catalog_only"
        else None,
        "records_accessed": _integer(attributes.get("records_accessed"), minimum=0),
        "account_resource": event["target"]["resource_type"] == "account",
    }


def _project(scope_id, evidence, allowed_scope_ids):
    if not _identifier(scope_id) or scope_id not in allowed_scope_ids:
        raise HypothesisInputError("hypothesis_scope_denied")
    if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
        raise HypothesisInputError("evidence_limit_exceeded")
    if len(_encoded(evidence)) > MAX_INPUT_BYTES:
        raise HypothesisInputError("evidence_bytes_exceeded")
    normalized = []
    extra = {}
    seen_ids, seen_events = set(), set()
    for row in evidence:
        if not isinstance(row, dict) or row.get("incident_id") != scope_id:
            raise HypothesisInputError("cross_scope_evidence")
        evidence_id, event_id = row.get("id"), row.get("event_id")
        if not _identifier(evidence_id) or not _identifier(event_id):
            raise HypothesisInputError("invalid_evidence_identifier")
        if evidence_id in seen_ids or event_id in seen_events:
            raise HypothesisInputError("duplicate_evidence_reference")
        seen_ids.add(evidence_id)
        seen_events.add(event_id)
        event = row.get("event")
        if not isinstance(event, dict) or event.get("event_id") != event_id:
            raise HypothesisInputError("event_reference_mismatch")
        timestamp = _timestamp(row.get("timestamp"))
        if timestamp != _timestamp(event.get("timestamp")):
            raise HypothesisInputError("event_timestamp_mismatch")
        try:
            canonical = CanonicalEvent.model_validate(event).model_dump(mode="json")
        except (ValidationError, ValueError, RecursionError, TypeError) as exc:
            raise HypothesisInputError("invalid_canonical_event") from exc
        relevance = row.get("relevance", "unreviewed")
        if relevance not in ("unreviewed", "relevant", "benign"):
            raise HypothesisInputError("invalid_relevance")
        normalized.append(
            {
                "id": evidence_id,
                "incident_id": scope_id,
                "event_id": event_id,
                "timestamp": timestamp.isoformat(),
                "event": canonical,
                "relevance": "unreviewed",
            }
        )
        extra[evidence_id] = {"relevance": relevance, "context": _context_fields(canonical)}
    normalized.sort(key=lambda row: (row["timestamp"], row["event_id"], row["id"]))
    try:
        context = build_context(
            "Assess bounded investigation hypotheses",
            scope_id,
            normalized,
            allowed_incident_ids=allowed_scope_ids,
        )
    except AnalysisInputError as exc:
        raise HypothesisInputError(str(exc)) from exc
    observations = [{**row, **extra[row["id"]]} for row in context.evidence]
    if len(_encoded(observations)) > MAX_CONTEXT_BYTES:
        raise HypothesisInputError("hypothesis_context_limit_exceeded")
    return observations


def gap_guidance(kind: str) -> dict:
    """A typed request for evidence, without asserting that the proposition occurred."""
    if not isinstance(kind, str) or kind not in _TITLES:
        raise HypothesisInputError("unknown_hypothesis_kind")
    return {
        "kind": kind,
        "title": _TITLES[kind],
        "missing_evidence": [
            {"category": name, "guidance": _GUIDANCE[name]} for name in _GAPS[kind]
        ],
    }


def _within(first, last, seconds=1800):
    delta = (_timestamp(last["timestamp"]) - _timestamp(first["timestamp"])).total_seconds()
    return 0 <= delta <= seconds


def _partial_sequence(claims, observations):
    stages = {"unrecognized_authentication": 0, "privilege_assigned": 1, "sensitive_access": 2}
    components = [
        (stages[claim["claim_type"]], observations[claim["evidence_ids"][0]])
        for claim in claims
        if claim["claim_type"] in stages
    ]
    for first, last in combinations(components, 2):
        left, right = sorted((first, last), key=lambda item: item[0])
        if (
            left[0] < right[0]
            and left[1]["user_id"] is not None
            and left[1]["user_id"] == right[1]["user_id"]
            and _within(left[1], right[1])
        ):
            return [left[1]["id"], right[1]["id"]]
    return []


def _approval_matches(approval, role):
    fields = approval["context"]
    session = (
        fields["approved_session"] if fields["approved_session_present"] else approval["session_id"]
    )
    return (
        approval["outcome"] == "success"
        and fields["source"] == "identity"
        and fields["context_type"] == "change_context"
        and fields["context_action"] == "change_approved"
        and fields["change_id"] is not None
        and fields["approved_minutes"] is not None
        and role["context"]["source"] == "identity"
        and approval["user_id"] is not None
        and approval["user_id"] == role["user_id"]
        and session is not None
        and session == role["session_id"]
        and fields["approved_role"] is not None
        and fields["approved_role"] == role["context"]["role"]
        and _within(approval, role, fields["approved_minutes"] * 60)
    )


def _approval_counterevidence(claims, observations):
    roles = [
        observations[claim["evidence_ids"][0]]
        for claim in claims
        if claim["claim_type"] == "privilege_assigned"
    ]
    citations = []
    for role in roles:
        approval = next(
            (
                candidate
                for candidate in observations.values()
                if _approval_matches(candidate, role)
            ),
            None,
        )
        if approval is None:
            return []
        citations.extend([approval["id"], role["id"]])
    return citations


def _job_key(observation):
    return observation["user_id"], observation["session_id"], observation["context"]["job_id"]


def _automation_observations(observations):
    """Sum all same-job queries once; one unbounded query prevents blanket explanation."""
    groups = defaultdict(list)
    for row in observations.values():
        if (
            row["context"]["source"] == "atlas"
            and row["event_type"] == "data_access"
            and row["action"] in {"query", "bulk_query"}
            and row["outcome"] == "success"
            and row["context"]["account_resource"]
        ):
            groups[_job_key(row)].append(row)
    support, counter, unresolved = [], [], False
    for key, queries in groups.items():
        candidates = [
            row
            for row in observations.values()
            if None not in key
            and _job_key(row) == key
            and row["context"]["source"] == "atlas"
            and row["context"]["context_type"] == "automation_context"
            and row["context"]["context_action"] == "job_scope_recorded"
            and row["outcome"] == "success"
            and (
                row["context"]["approved_record_limit"] is not None
                or row["context"]["approved_scope"] is not None
            )
            and all(_within(row, query) for query in queries)
        ]
        # Conflicting or repeated scope records require human reconciliation.
        if len(candidates) != 1:
            unresolved = True
            continue
        context = candidates[0]
        fields = context["context"]
        cites = [context["id"], *(row["id"] for row in queries)]
        if fields["approved_scope"] == "public_catalog_only":
            support.extend(cites)
        elif any(row["context"]["records_accessed"] is None for row in queries):
            unresolved = True
        elif (
            sum(row["context"]["records_accessed"] for row in queries)
            > fields["approved_record_limit"]
        ):
            support.extend(cites)
        else:
            counter.extend(cites)
    if support:
        return "SUPPORTED", support, []
    if groups and not unresolved and counter:
        return "CONTRADICTED", [], counter
    return "INSUFFICIENT_EVIDENCE", [], []


def build_ledger(
    scope_id: str,
    evidence: list[dict],
    *,
    allowed_scope_ids: set[str] | frozenset[str],
    scenario_id: str | None = None,
    scenario_version: str | None = None,
    ruleset_digest: str | None = None,
) -> dict:
    """Derive four stable propositions from validated scoped evidence only."""
    for value in (scenario_id, scenario_version):
        if value is not None and not _identifier(value):
            raise HypothesisInputError("invalid_hypothesis_provenance")
    if ruleset_digest is not None and (
        not isinstance(ruleset_digest, str) or re.fullmatch(r"[a-f0-9]{64}", ruleset_digest) is None
    ):
        raise HypothesisInputError("invalid_hypothesis_provenance")
    projected = _project(scope_id, evidence, allowed_scope_ids)
    digest = hashlib.sha256(_encoded(projected)).hexdigest()
    active = [row for row in projected if row["relevance"] != "benign"]
    observations = {row["id"]: row for row in active}
    claims = supported_claims(active)
    sequences = [claim for claim in claims if claim["claim_type"] == "suspicious_sequence"]
    unfamiliar = [
        eid
        for claim in claims
        if claim["claim_type"] == "unrecognized_authentication"
        for eid in claim["evidence_ids"]
    ]
    sequence_ids = (
        sequences[0]["evidence_ids"] if sequences else _partial_sequence(claims, observations)
    )
    approval_ids = _approval_counterevidence(claims, observations)
    derived = {
        "account_compromise": (
            "PARTIALLY_SUPPORTED" if unfamiliar else "INSUFFICIENT_EVIDENCE",
            unfamiliar,
            [],
        ),
        "suspicious_privilege_sequence": (
            "SUPPORTED"
            if sequences
            else "PARTIALLY_SUPPORTED"
            if sequence_ids
            else "INSUFFICIENT_EVIDENCE",
            sequence_ids,
            [],
        ),
        "unapproved_privilege_change": (
            "CONTRADICTED" if approval_ids else "INSUFFICIENT_EVIDENCE",
            [],
            approval_ids,
        ),
        "unexplained_bulk_access": _automation_observations(observations),
    }
    provenance = {
        "derivation_version": DERIVATION_VERSION,
        "scope_id": scope_id,
        "evidence_digest": digest,
    }
    for name, value in (
        ("scenario_id", scenario_id),
        ("scenario_version", scenario_version),
        ("ruleset_digest", ruleset_digest),
    ):
        if value is not None:
            provenance[name] = value
    order = {row["id"]: index for index, row in enumerate(projected)}
    items = []
    for kind, (status, supporting, contradicting) in derived.items():
        citations = set(supporting) | set(contradicting)
        items.append(
            {
                "id": "HYP-" + hashlib.sha256(f"{scope_id}:{kind}".encode()).hexdigest()[:16],
                "kind": kind,
                "title": _TITLES[kind],
                "epistemic_status": status,
                "supporting_evidence_ids": sorted(set(supporting), key=order.__getitem__),
                "contradicting_evidence_ids": sorted(set(contradicting), key=order.__getitem__),
                "missing_evidence": gap_guidance(kind)["missing_evidence"]
                if status in {"INSUFFICIENT_EVIDENCE", "PARTIALLY_SUPPORTED"}
                else [],
                "related_finding_ids": [],
                "provenance": copy.deepcopy(provenance),
                "first_observed_at": min(
                    (observations[eid]["timestamp"] for eid in citations), default=None
                ),
                "as_of": projected[-1]["timestamp"] if projected else None,
            }
        )
    result = {"scope_id": scope_id, "evidence_digest": digest, "items": items}
    if len(_encoded(result)) > MAX_LEDGER_BYTES:
        raise HypothesisInputError("hypothesis_ledger_limit_exceeded")
    return result


def validate_hypothesis(snapshot: dict, ledger: dict) -> dict:
    """Accept only an exact candidate from the freshly server-derived ledger."""
    if not isinstance(snapshot, dict) or not isinstance(ledger, dict):
        raise HypothesisInputError("invalid_hypothesis_snapshot")
    for candidate in ledger.get("items", []):
        if snapshot == candidate and _encoded(snapshot) == _encoded(candidate):
            return copy.deepcopy(candidate)
    raise HypothesisInputError("unsupported_hypothesis_snapshot")
