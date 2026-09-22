"""Public policy tests use a database override, never permit SQLite in public settings."""

import importlib
import logging

import pytest
from aegisgraph import analyst, config, main
from aegisgraph import models as m
from aegisgraph import services as svc
from aegisgraph.db import Base, get_db, make_engine
from aegisgraph.public_security import PUBLIC_QUESTIONS, PublicBudget
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ORIGIN = "https://frontend.example"
CASE = "INC-fe8fa4b9508c"


@pytest.fixture(scope="module")
def public_database(tmp_path_factory):
    engine = make_engine(f"sqlite:///{tmp_path_factory.mktemp('public-api') / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        svc.seed_database(session)
        svc.execute_evaluations(session)
    yield engine
    engine.dispose()


@pytest.fixture
def public_client(public_database, monkeypatch):
    public_settings = config.Settings(
        app_mode="public_demo",
        database_url="postgresql://demo:fixture-password@database.example/demo",
        allowed_origins=(ORIGIN,),
        allowed_hosts=("api.example", "healthcheck.railway.app"),
    )
    # Reload the real application so docs, CORS and host policy are built with
    # production settings. Only get_db is overridden for isolated fixture storage.
    original_app = main.app
    original_settings = main.settings
    monkeypatch.setattr(config, "settings", public_settings)
    monkeypatch.setattr(svc, "settings", public_settings)
    importlib.reload(main)

    def override():
        with Session(public_database) as session:
            yield session

    main.app.dependency_overrides[get_db] = override
    try:
        with TestClient(
            main.app, base_url="https://api.example", client=("192.0.2.10", 40000)
        ) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()
        main.app = original_app
        main.settings = original_settings


def test_public_reads_flagship_navigation_saved_evaluations_and_runtime(public_client):
    client = public_client
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    runtime = client.get("/api/runtime").json()
    expected_contract = {
        "app_mode": "public_demo",
        "read_only": True,
        "analyst_provider": "deterministic",
        "questions": list(PUBLIC_QUESTIONS),
    }
    assert {key: runtime[key] for key in expected_contract} == expected_contract
    assert client.get("/api/overview").json()["counts"]["events"] == 4026
    assert client.get("/api/incidents").json()["items"][0]["id"] == CASE
    case = client.get(f"/api/incidents/{CASE}").json()
    assert len(case["evidence"]) == 26
    assert len(case["alerts"]) == 10
    assert case["correlation"]["distinct_rule_count"] == 9
    event = client.get(f"/api/events/{case['evidence'][0]['event_id']}").json()
    assert event["event_id"] == case["evidence"][0]["event_id"]
    entity = client.get(f"/api/entities/{case['entities'][0]['id']}").json()
    assert entity["events"]
    assert client.get("/api/events?q=USR-004&limit=7").json()["items"]
    assert len(client.get("/api/detections").json()["items"]) == 10
    assert client.get("/api/alerts").json()["total"] == 10
    assert client.get("/api/evaluations").json()["passed"] == 28
    assert client.get("/api/evaluations/live").json()["status"] == "not_run"


def test_public_analyst_is_grounded_credential_free_and_never_persists(
    public_client, public_database, monkeypatch
):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Public analyst attempted configured or external provider selection")

    monkeypatch.setattr(analyst, "configured_provider", forbidden)
    monkeypatch.setattr(analyst.OpenAIProvider, "generate", forbidden)
    path = f"/api/incidents/{CASE}"
    before = public_client.get(path).json()
    tables = [
        m.Incident,
        m.Evidence,
        m.Finding,
        m.Note,
        m.Report,
        m.Analysis,
        m.Audit,
        m.EvaluationRun,
    ]

    def counts():
        with Session(public_database) as db:
            return [db.scalar(select(func.count()).select_from(table)) for table in tables]

    before_counts = counts()
    answer = public_client.post(
        path + "/analysis", headers={"Origin": ORIGIN}, json={"question": PUBLIC_QUESTIONS[0]}
    )
    assert answer.status_code == 200
    grounded = answer.json()
    assert grounded["status"] == "answered"
    assert grounded["provider"] == "deterministic"
    assert grounded["validation_errors"] == []
    assert grounded["findings"]
    allowed = {item["id"] for item in before["evidence"]}
    assert all(set(item["evidence_ids"]).issubset(allowed) for item in grounded["findings"])
    insufficient = public_client.post(
        path + "/analysis", headers={"Origin": ORIGIN}, json={"question": PUBLIC_QUESTIONS[1]}
    ).json()
    assert insufficient["status"] == "insufficient_evidence"
    assert insufficient["provider"] == "deterministic"
    assert insufficient["findings"] == []
    assert insufficient["missing_evidence"]
    assert public_client.get(path).json() == before
    assert counts() == before_counts


@pytest.mark.parametrize(
    "method,path",
    [
        ("PATCH", f"/api/incidents/{CASE}"),
        ("PUT", f"/api/incidents/{CASE}"),
        ("DELETE", f"/api/incidents/{CASE}/evidence/EVD-example"),
        ("PATCH", f"/api/incidents/{CASE}/evidence/EVD-example"),
        ("POST", f"/api/incidents/{CASE}/findings"),
        ("PATCH", f"/api/incidents/{CASE}/findings/FND-example"),
        ("POST", f"/api/incidents/{CASE}/notes"),
        ("POST", f"/api/incidents/{CASE}/report"),
        ("POST", f"/api/incidents/{CASE}/report/approve"),
        ("POST", "/api/evaluations/run"),
        ("PATCH", "/api/detections/AUTH-001"),
        ("DELETE", "/api/audit"),
        ("POST", "/api/seed"),
        ("POST", "/api/reset"),
        ("POST", "/api/demo-reset"),
        ("POST", "/api/admin/reset"),
        ("POST", "/unknown-future-write"),
        ("POST", f"/api/incidents/{CASE}/analysis/"),
        ("TRACE", "/health"),
    ],
)
def test_public_default_deny_mutation_matrix(public_client, method, path):
    response = public_client.request(
        method, path, headers={"Origin": ORIGIN}, json={"status": "resolved", "secret": "fixture"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Public demo is read-only; this action is unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_public_analysis_rejects_unbounded_questions_and_scope_input_without_echo(public_client):
    path = f"/api/incidents/{CASE}/analysis"
    for payload in (
        {"question": "arbitrary private input"},
        {"question": PUBLIC_QUESTIONS[0], "evidence_ids": ["foreign-private-id"]},
        {"question": {"private": "nested-input"}},
    ):
        response = public_client.post(path, headers={"Origin": ORIGIN}, json=payload)
        assert response.status_code == 422
        assert "private" not in response.text
    assert (
        public_client.post(
            "/api/incidents/nonexistent/analysis",
            headers={"Origin": ORIGIN},
            json={"question": PUBLIC_QUESTIONS[0]},
        ).status_code
        == 404
    )


def test_public_origin_and_host_controls(public_client):
    path = f"/api/incidents/{CASE}/analysis"
    payload = {"question": PUBLIC_QUESTIONS[0]}
    assert public_client.post(path, json=payload).status_code == 403
    assert (
        public_client.post(
            path, headers={"Origin": "https://unrelated.example"}, json=payload
        ).status_code
        == 403
    )
    assert (
        public_client.get(
            "/api/runtime", headers={"Origin": "https://unrelated.example"}
        ).status_code
        == 403
    )
    response = public_client.get("/api/runtime", headers={"Origin": ORIGIN})
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-credentials" not in response.headers
    preflight = public_client.options(
        path,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert "PATCH" not in preflight.headers["access-control-allow-methods"]
    assert (
        public_client.options(
            path, headers={"Origin": ORIGIN, "Access-Control-Request-Method": "PATCH"}
        ).status_code
        == 400
    )
    assert public_client.get("/health", headers={"Host": "unrelated.example"}).status_code == 400
    assert (
        public_client.get("/health", headers={"Host": "healthcheck.railway.app"}).status_code == 200
    )


def test_public_docs_disabled_bodies_bounded_and_query_errors_redacted(public_client):
    for path in ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"]:
        assert public_client.get(path).status_code == 404
    response = public_client.post(
        f"/api/incidents/{CASE}/analysis", headers={"Origin": ORIGIN}, content=b"x" * 8193
    )
    assert response.status_code == 413
    assert public_client.get("/api/events?limit=private-value").json() == {
        "detail": "Request input is invalid"
    }
    assert public_client.get("/api/events?q=" + "x" * 2050).status_code == 414
    assert public_client.get("/api/runtime", headers={"X-Extra": "x" * 16385}).status_code == 431


def test_public_unexpected_error_and_logs_do_not_disclose_values(public_client, caplog):
    def broken_database():
        raise RuntimeError("private-secret https://user:secret@private-host/ local/private/path")

    main.app.dependency_overrides[get_db] = broken_database
    with caplog.at_level(logging.INFO, logger="aegisgraph.http"):
        response = public_client.get("/health?private-secret=ignored")
    assert response.status_code == 500
    assert response.json() == {"detail": "Request could not be completed"}
    http_messages = " ".join(
        row.getMessage() for row in caplog.records if row.name == "aegisgraph.http"
    )
    for value in ["private-secret", "private-host", "local/private/path", "Traceback"]:
        assert value not in response.text
        assert value not in http_messages


def test_public_readiness_fails_closed_when_flagship_data_is_missing(public_client, monkeypatch):
    from aegisgraph import deployment

    monkeypatch.setattr(deployment, "dataset_status", lambda db: {"ready": False})
    response = public_client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_public_analyst_rate_limit_ignores_forwarded_identity(public_client):
    path = f"/api/incidents/{CASE}/analysis"
    for index in range(4):
        response = public_client.post(
            path,
            json={"question": PUBLIC_QUESTIONS[0]},
            headers={"Origin": ORIGIN, "X-Forwarded-For": f"192.0.2.{index + 1}"},
        )
        assert response.status_code == 200
    limited = public_client.post(
        path,
        json={"question": PUBLIC_QUESTIONS[0]},
        headers={"Origin": ORIGIN, "X-Forwarded-For": "198.51.100.1"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


def test_public_budget_has_fixed_memory_global_search_and_concurrency_caps():
    now = [10.0]
    budget = PublicBudget(clock=lambda: now[0])
    for _ in range(20):
        assert budget.enter("search") is None
        budget.leave("search")
    assert budget.enter("search") == (429, 1)
    now[0] += 1
    assert budget.enter("search") is None
    budget.leave("search")
    assert len(budget.buckets) == 5
    for _ in range(8):
        assert budget.enter("read") is None
    assert budget.enter("read") == (503, 1)
    for _ in range(8):
        budget.leave("read")
    assert budget.enter("analysis") is None
    assert budget.enter("analysis") is None
    assert budget.enter("analysis") == (503, 1)
    budget.leave("analysis")
    budget.leave("analysis")
    assert budget.active == budget.active_analysis == 0
