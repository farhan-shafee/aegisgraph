import copy
import json

import httpx
import pytest
from aegisgraph.analyst import DeterministicProvider, OpenAIProvider, ProviderError, build_context
from aegisgraph.evaluations import load_fixtures
from aegisgraph.live_evaluations import (
    execute_live_case,
    run_boundary_checks,
    sanitize_attempt,
    summarize_attempts,
)

FIXTURE = load_fixtures()


def response_body(draft):
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(draft)}],
            }
        ],
    }


def provider_with_response(callback):
    return OpenAIProvider(
        "fixture-key-never-real", "fixture-model", transport=httpx.MockTransport(callback)
    )


@pytest.mark.parametrize(
    "code,expected",
    [
        ("insufficient_quota", "provider_quota_exhausted"),
        ("rate_limit_exceeded", "provider_rate_limited"),
        ("invalid_api_key", "provider_authentication_failed"),
        ("model_not_found", "provider_model_unavailable"),
        ("invalid_json_schema", "provider_schema_rejected"),
    ],
)
def test_error_classifier_reads_bounded_stream_and_never_exposes_message(code, expected):
    context = build_context(
        "What happened?",
        FIXTURE["incident_id"],
        FIXTURE["evidence"],
        allowed_incident_ids={FIXTURE["incident_id"]},
    )
    provider = provider_with_response(
        lambda _: httpx.Response(
            429,
            json={
                "error": {
                    "code": code,
                    "message": "sensitive-upstream-canary",
                    "param": "sensitive-param-canary",
                }
            },
            headers={"retry-after": "12", "authorization": "sensitive-header-canary"},
        )
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate(context)
    error = caught.value
    assert error.code == expected
    assert error.provider_code == code
    assert error.http_status == 429
    assert error.diagnostics["json_parseable"] is True
    assert error.diagnostics["error_object_present"] is True
    assert error.diagnostics["error_code_present"] is True
    assert error.diagnostics["retry_after_seconds"] == 12
    assert error.diagnostics["response_bytes"] > 0
    assert "sensitive" not in str(error.__dict__)


def test_unknown_429_body_has_neutral_code_and_safe_metadata():
    context = build_context(
        "What happened?",
        FIXTURE["incident_id"],
        FIXTURE["evidence"],
        allowed_incident_ids={FIXTURE["incident_id"]},
    )
    provider = provider_with_response(
        lambda _: httpx.Response(
            429, text="unknown-sensitive-body", headers={"retry-after": "secret-value-canary"}
        )
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate(context)
    assert caught.value.code == "provider_request_limited"
    assert caught.value.provider_code is None
    assert caught.value.diagnostics == {
        "response_bytes": 22,
        "json_parseable": False,
        "error_object_present": False,
        "error_code_present": False,
        "retry_after_seconds": None,
    }
    assert "canary" not in str(caught.value.__dict__)


def test_custom_provider_error_is_sanitized():
    error = ProviderError("private-secret-error", provider_code="private-secret-code")
    assert error.code == "provider_execution_failed"
    assert error.provider_code is None
    assert "private-secret" not in str(error.__dict__)


def test_live_case_mock_preserves_boundary_without_network():
    captured = []

    def handle(request):
        payload = json.loads(request.content)
        data = json.loads(payload["input"][0]["content"][0]["text"])
        captured.append(data)
        return httpx.Response(
            200,
            json=response_body(
                {
                    "disposition": "answer",
                    "claims": [data["supported_claims"][0]],
                    "missing_evidence": ["verified_actor_attribution"],
                    "recommended_next_steps": [],
                }
            ),
        )

    rows = copy.deepcopy(FIXTURE["evidence"])
    provider = provider_with_response(handle)
    result = execute_live_case("LIVE-INJECTION", FIXTURE["incident_id"], rows, provider, 1)
    assert result["status"] == "answered"
    assert result["injected_fields_excluded"] is True
    assert result["incident_and_evidence_unchanged"] is True
    assert result["citations_within_bounded_context"] is True
    assert len(captured) == 1
    assert "INJECTION-CANARY" not in json.dumps(captured)
    assert "fixture-key" not in json.dumps(result) and "fixture-model" not in json.dumps(result)


def test_false_premise_guard_does_not_mislabel_model_behavior_as_pass():
    def handle(request):
        data = json.loads(json.loads(request.content)["input"][0]["content"][0]["text"])
        return httpx.Response(
            200,
            json=response_body(
                {
                    "disposition": "answer",
                    "claims": [data["supported_claims"][0]],
                    "missing_evidence": [],
                    "recommended_next_steps": [],
                }
            ),
        )

    attempt = execute_live_case(
        "LIVE-MALWARE",
        FIXTURE["incident_id"],
        FIXTURE["evidence"],
        provider_with_response(handle),
        1,
    )
    assert attempt["status"] == "insufficient_evidence"
    assert attempt["model_withheld_false_premise"] is False
    result = summarize_attempts(FIXTURE["incident_id"], FIXTURE["evidence"], [attempt])
    malware = next(row for row in result["cases"] if row["id"] == "LIVE-MALWARE")
    assert malware["passed"] is False


def test_partial_summary_keeps_blocked_and_skipped_separate_from_local_checks():
    context = build_context(
        "What happened?",
        FIXTURE["incident_id"],
        FIXTURE["evidence"],
        allowed_incident_ids={FIXTURE["incident_id"]},
    )
    successful = provider_with_response(
        lambda _: httpx.Response(200, json=response_body(DeterministicProvider().generate(context)))
    )
    success = execute_live_case(
        "LIVE-GROUNDED", FIXTURE["incident_id"], FIXTURE["evidence"], successful, 1
    )
    unavailable = provider_with_response(
        lambda _: httpx.Response(
            429, json={"error": {"code": "insufficient_quota", "message": "secret-canary"}}
        )
    )
    blocked = execute_live_case(
        "LIVE-MALWARE", FIXTURE["incident_id"], FIXTURE["evidence"], unavailable, 2
    )
    result = summarize_attempts(FIXTURE["incident_id"], FIXTURE["evidence"], [success, blocked])
    assert result["status"] == "partial"
    assert result["live_cases"] == {"total": 2, "passed": 1, "failed": 1, "skipped": 1}
    assert result["boundary_cases"] == {"total": 5, "passed": 5, "failed": 0}
    assert result["provider_requests_attempted"] == 2
    assert result["provider_requests_succeeded"] == 1
    assert result["total"] == result["passed"] + result["failed"] == 7
    assert "secret-canary" not in json.dumps(result)


def test_safe_records_whitelist_values_not_only_field_names():
    record = {
        "case_id": "LIVE-GROUNDED",
        "provider": "openai",
        "status": "answered",
        "started_at": "secret-canary",
        "safe_error": "secret-canary",
        "provider_error_code": "secret-canary",
        "validation_errors": ["secret-canary"],
        "reason": "secret-canary",
        "model": "secret-canary",
        "raw": "secret-canary",
        "request_headers": {"authorization": "secret-canary"},
        "elapsed_ms": "secret-canary",
    }
    assert sanitize_attempt(record) == {
        "case_id": "LIVE-GROUNDED",
        "provider": "openai",
        "status": "answered",
    }


def test_local_checks_do_not_call_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Local isolation checks attempted a live call")

    monkeypatch.setattr(OpenAIProvider, "generate", forbidden)
    results = run_boundary_checks(FIXTURE["incident_id"], FIXTURE["evidence"])
    assert len(results) == 5 and all(row["passed"] for row in results)


def test_boundary_failure_cannot_be_hidden_by_live_summary(monkeypatch):
    from aegisgraph import live_evaluations

    checks = run_boundary_checks(FIXTURE["incident_id"], FIXTURE["evidence"])
    checks[0].update(passed=False, status="failed")
    monkeypatch.setattr(live_evaluations, "run_boundary_checks", lambda *_: checks)
    result = summarize_attempts(FIXTURE["incident_id"], FIXTURE["evidence"], [])
    assert result["status"] == "failed"
    assert result["boundary_cases"] == {"total": 5, "passed": 4, "failed": 1}
