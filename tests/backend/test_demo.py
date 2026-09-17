import json
import os

import httpx
import pytest
from aegisgraph import demo
from aegisgraph.db import make_engine
from sqlalchemy import text


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://aegisgraph:public-demo@127.0.0.1:5432/aegisgraph",
        "postgresql+psycopg://aegisgraph:public-demo@127.0.0.1:5432/production",
        "postgresql+psycopg://aegisgraph:public-demo@192.0.2.10:5432/aegisgraph_demo",
        "postgresql+psycopg://aegisgraph:public-demo@127.0.0.1:5432/aegisgraph_demo?host=192.0.2.10",
        "postgresql+psycopg://other:public-demo@127.0.0.1:5432/aegisgraph_demo",
        "sqlite:///./aegisgraph.db",
        "sqlite:///:memory:",
        "not-a-database-url",
    ],
)
def test_arbitrary_destructive_targets_are_rejected_without_echoing_values(url):
    with pytest.raises(demo.DemoCommandError) as error:
        demo.validate_reset_target(url)
    assert url not in str(error.value)
    assert "public-demo" not in str(error.value)


def test_reserved_targets_and_provider_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_ROOT", tmp_path)
    monkeypatch.setenv("DATABASE_URL", "not-used-by-demo-reset")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-a-real-key")
    url = demo.demo_database_url()
    demo.validate_reset_target(url)
    assert url.endswith("/.runtime/aegisgraph-demo.db")
    demo.validate_reset_target(demo.demo_database_url(55432))
    environment = demo.child_environment(url)
    assert environment["AI_PROVIDER"] == "deterministic"
    assert environment["AEGISGRAPH_LOAD_ENV"] == "false"
    assert "OPENAI_API_KEY" not in environment
    assert environment["DATABASE_URL"] == url


def test_symlink_or_hardlink_database_cannot_escape_reserved_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_ROOT", tmp_path)
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    external = tmp_path / "important.db"
    external.write_bytes(b"preserve")
    target = runtime / "aegisgraph-demo.db"
    try:
        os.link(external, target)
    except OSError:
        pytest.skip("Filesystem does not support hard links")
    with pytest.raises(demo.DemoCommandError):
        demo.demo_database_url()
    with pytest.raises(demo.DemoCommandError):
        demo.validate_reset_target(f"sqlite:///{target.as_posix()}")
    assert external.read_bytes() == b"preserve"


def test_reset_executes_clean_migrations_seed_and_deterministic_evaluations(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_ROOT", tmp_path)
    monkeypatch.setenv("DATABASE_URL", "unused-invalid-configured-database")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    result = demo.reset_demo()
    assert result["status"] == "ready"
    assert (result["events"], result["alerts"], result["incidents"]) == (4026, 10, 1)
    assert result["evaluations"]["provider"] == "deterministic"
    assert result["evaluations"]["total"] >= 28
    assert result["evaluations"]["failed"] == 0
    assert "OPENAI_API_KEY" not in json.dumps(result)
    with make_engine(demo.demo_database_url()).connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM evaluation_runs")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM events")) == 4026


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid",
        "http://user:fixture-secret@127.0.0.1:8000",
        "http://127.0.0.1:8000?key=fixture-secret",
    ],
)
def test_health_refuses_nonlocal_or_credential_bearing_urls(url):
    with pytest.raises(demo.DemoCommandError) as error:
        demo.check_demo_health(url)
    assert "fixture-secret" not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:not-a-port",
        "http://127.0.0.1:99999",
        "http://[::1",
    ],
)
def test_health_malformed_url_returns_fixed_error_without_echoing_input(url):
    with pytest.raises(demo.DemoCommandError) as error:
        demo.check_demo_health(url)
    assert str(error.value) == "Demo health requires a valid loopback HTTP API URL."
    assert url not in str(error.value)


def test_health_uses_explicit_deterministic_provider_and_safe_output(monkeypatch):
    from aegisgraph.analyst import DeterministicProvider

    case = {"id": "INC-FIXTURE", "evidence": [{}] * 26, "alerts": [{}] * 10}
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "/health": {"status": "ok"},
                "/api/overview": {"counts": {"events": 4026, "alerts": 10, "incidents": 1}},
                "/api/incidents": {
                    "items": [
                        {
                            "id": case["id"],
                            "title": "Suspected compromise of Atlas engineer account",
                        }
                    ]
                },
                "/api/incidents/INC-FIXTURE": case,
            }[request.url.path],
        )
    )
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:8000")
    monkeypatch.setattr(demo.httpx, "Client", lambda **_kwargs: client)

    def analyze(*_args, **kwargs):
        assert isinstance(kwargs["provider"], DeterministicProvider)
        return {"status": "answered", "findings": [{"statement": "fixture"}]}

    monkeypatch.setattr("aegisgraph.analyst.analyze", analyze)
    result = demo.check_demo_health()
    assert result["status"] == "healthy"
    assert result["live_provider_called"] is False
    assert all(check["passed"] for check in result["checks"])
