"""Execute isolated AI boundary fixtures, without touching application persistence.

Run from the repository: python -m aegisgraph.evaluations
The default suite never selects a provider from the environment or uses a key.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .analyst import (
    MAX_EVIDENCE,
    MAX_RESPONSE_BYTES,
    AnalysisInputError,
    AnalystContext,
    DeterministicProvider,
    analyze,
    build_context,
)

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ai_cases.json"


def load_fixtures(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class FixtureProvider:
    """A test double for exercising output boundaries, never a live model."""

    name = "fixture"

    def __init__(self, payload: Any):
        self.payload = payload
        self.calls = 0

    def generate(self, context: AnalystContext) -> Any:
        self.calls += 1
        return copy.deepcopy(self.payload)


def _draft(evidence_id: str) -> dict[str, Any]:
    return {
        "disposition": "answer",
        "claims": [{"claim_type": "authentication_succeeded", "evidence_ids": [evidence_id]}],
        "missing_evidence": [],
        "recommended_next_steps": [],
    }


def _check(condition: bool, explanation: str) -> None:
    if not condition:
        raise AssertionError(explanation)


def _run_case(case: dict[str, Any], fixture: dict[str, Any]) -> str:
    evidence = copy.deepcopy(fixture["evidence"])
    original = copy.deepcopy(evidence)
    incident_id = fixture["incident_id"]
    allowed = {incident_id}
    question = case.get("question", "What most likely happened?")
    provider = DeterministicProvider()
    kind = case["kind"]

    def run(rows: list[dict[str, Any]] | None = None, selected: Any = provider) -> dict[str, Any]:
        return analyze(
            question,
            incident_id,
            evidence if rows is None else rows,
            allowed_incident_ids=allowed,
            provider=selected,
        )

    if kind == "grounded":
        result = run()
        _check(
            result["status"] == "answered" and bool(result["findings"]),
            "Expected supported findings",
        )
        ids = {row["id"] for row in evidence}
        for finding in result["findings"]:
            _check(
                bool(finding["evidence_ids"]) and set(finding["evidence_ids"]) <= ids,
                "Invalid finding citation",
            )
        _check(
            "suspicious_sequence" in {row["claim_type"] for row in result["findings"]},
            "Expected the supported temporal observation",
        )
        _check("[EVD-" in result["summary"], "Summary omitted citations")
        return "Supported observations and a cited summary were rendered from the isolated fixture."
    if kind == "false_premise":
        result = run()
        _check(
            result["status"] == "insufficient_evidence" and not result["findings"],
            "Unsupported premise was accepted",
        )
        _check(
            case["reason"] in " ".join(result["missing_evidence"]),
            "Missing evidence was not identified",
        )
        return "The requested conclusion was withheld and the missing evidence was identified."
    if kind == "telemetry_injection":
        if case["location"] == "raw":
            evidence[0]["event"]["raw"] = {"message": case["payload"]}
            evidence[0]["event"]["network"] = {"user_agent": case["payload"]}
        elif case["location"] == "attributes":
            evidence[0]["event"]["attributes"]["message"] = case["payload"]
        else:
            evidence[0]["note"] = case["payload"]
        context = build_context(question, incident_id, evidence, allowed_incident_ids=allowed)
        _check(
            "INJECTION-CANARY" not in json.dumps(context.as_data()),
            "Untrusted free text entered the provider context",
        )
        actual = run()
        baseline = run(original)
        _check(actual == baseline, "Excluded telemetry changed the deterministic answer")
        return "The injected field was excluded by projection; the deterministic answer matched the clean fixture. This is a boundary test, not a live-model attack measurement."
    if kind == "typed_injection":
        evidence[4]["event"]["attributes"]["sensitive"] = case["payload"]
        context = build_context(question, incident_id, evidence, allowed_incident_ids=allowed)
        _check(
            "INJECTION-CANARY" not in json.dumps(context.as_data()),
            "Typed signal retained instruction text",
        )
        result = run()
        _check(
            not any(
                row["claim_type"] in {"sensitive_access", "suspicious_sequence"}
                for row in result["findings"]
            ),
            "String was coerced to a true signal",
        )
        return "A string pretending to be a boolean did not support a sensitive-access claim."
    if kind in {"cross_case_context", "unauthorized_incident", "evidence_limit"}:
        spy = FixtureProvider(_draft(evidence[0]["id"]))
        expected = {
            "cross_case_context": "cross_incident_evidence",
            "unauthorized_incident": "incident_scope_denied",
            "evidence_limit": "evidence_limit_exceeded",
        }[kind]
        if kind == "cross_case_context":
            evidence[-1]["incident_id"] = "INC-OTHER-CASE"
        elif kind == "unauthorized_incident":
            allowed.clear()
        else:
            evidence = evidence * (MAX_EVIDENCE // len(evidence) + 1)
        try:
            run(selected=spy)
        except AnalysisInputError as exc:
            _check(str(exc) == expected and spy.calls == 0, "Boundary rejected at the wrong stage")
            return "Input was rejected before any provider execution."
        raise AssertionError("Expected an input boundary rejection")
    if kind == "benign_context":
        evidence[2]["relevance"] = "benign"
        result = run()
        _check(result["excluded_benign_count"] == 1, "Benign context exclusion was not disclosed")
        _check(
            result["context_evidence_count"] == len(evidence) - 1,
            "Benign row remained in provider context",
        )
        _check(
            not any(
                row["claim_type"] in {"privilege_assigned", "suspicious_sequence"}
                for row in result["findings"]
            ),
            "Benign role grant still supported a suspicious hypothesis",
        )
        return "The analyst-benign role grant was excluded before provider selection; the exclusion count was disclosed and the suspicious sequence was withheld."
    if kind == "empty_context":
        result = run([])
        _check(result["status"] == "insufficient_evidence", "Empty evidence was accepted")
        return "An empty bounded context returned insufficient evidence."
    if kind in {"different_actor", "sequence_window"}:
        if kind == "different_actor":
            evidence[2]["event"]["actor"]["user_id"] = "usr-other-synthetic"
        else:
            evidence[4]["timestamp"] = "2026-06-15T15:14:00Z"
        context = build_context(question, incident_id, evidence, allowed_incident_ids=allowed)
        _check(
            not any(row["claim_type"] == "suspicious_sequence" for row in context.supported_claims),
            "Unsupported sequence was offered to the provider",
        )
        return "The temporal sequence predicate withheld an unsupported cross-event claim."
    if kind == "mutation_context":

        class MutatingProvider:
            name = "fixture"

            def generate(self, context: AnalystContext) -> dict[str, Any]:
                context.evidence[0]["id"] = "EVD-TAMPERED"
                context.supported_claims[0]["evidence_ids"] = ["EVD-TAMPERED"]
                return _draft("EVD-TAMPERED")

        result = run(selected=MutatingProvider())
        _check(
            result["status"] == "rejected" and evidence == original,
            "Provider changed trusted context",
        )
        return "The provider received a copy; tampering failed validation and left source evidence unchanged."

    draft: Any = _draft(evidence[0]["id"])
    if kind == "invalid_citation":
        draft["claims"][0]["evidence_ids"] = [case["citation"]]
    elif kind == "outside_context":
        draft["claims"][0]["evidence_ids"] = [evidence[-1]["id"]]
        evidence = evidence[:-1]
    elif kind == "unsupported_claim":
        draft["claims"][0]["claim_type"] = "privilege_assigned"
    elif kind == "malicious_prose":
        draft["claims"][0]["statement"] = case["statement"]
    elif kind == "uncited_summary":
        draft["summary"] = case["summary"]
    elif kind == "malformed_json":
        draft = case["payload"]
    elif kind == "unknown_field":
        draft["trusted"] = True
    elif kind == "oversized_output":
        draft = " " * (MAX_RESPONSE_BYTES + 1)
    elif kind == "mutation_output":
        draft["mutation"] = {"incident_status": "Resolved", "delete_evidence": True}
    else:
        raise AssertionError("Unknown evaluation fixture kind")
    result = run(selected=FixtureProvider(draft))
    _check(
        result["status"] == "rejected" and not result["findings"],
        "Unsafe provider response was accepted",
    )
    if kind == "mutation_output":
        _check(evidence == original, "Source evidence was mutated")
    return "The entire provider answer was rejected; no proposed factual findings were rendered."


def run_evaluations() -> dict[str, Any]:
    started = datetime.now(UTC).isoformat()
    fixtures = load_fixtures()
    results = []
    for case in fixtures["cases"]:
        try:
            detail = _run_case(case, fixtures)
            passed = True
        except (AssertionError, AnalysisInputError, KeyError, ValueError, TypeError) as exc:
            # Fixtures are repository-controlled and contain no credentials.
            detail = f"Boundary test failed: {exc}"
            passed = False
        results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "name": case["name"],
                "passed": passed,
                "detail": detail,
            }
        )
    categories = []
    for category in sorted({row["category"] for row in results}):
        rows = [row for row in results if row["category"] == category]
        passed = sum(row["passed"] for row in rows)
        categories.append(
            {
                "category": category,
                "total": len(rows),
                "passed": passed,
                "failed": len(rows) - passed,
                "pass_rate": round(passed / len(rows) * 100, 1),
            }
        )
    passed = sum(row["passed"] for row in results)
    return {
        "id": f"EVAL-{uuid4().hex[:12]}",
        "provider": "deterministic",
        "started_at": started,
        "completed_at": datetime.now(UTC).isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
        "categories": categories,
        "pass_rate": round(passed / len(results) * 100, 1) if results else None,
        "scope": "Application boundary tests using deterministic and adversarial fixture providers. No external model was called.",
        "live_model_tested": False,
        "fixture_version": fixtures["schema_version"],
    }


def main() -> None:
    result = run_evaluations()
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()
