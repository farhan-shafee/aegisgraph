"""Explicitly disposable local demo commands; never infer reset from DATABASE_URL."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy.engine import make_url

from .config import ROOT

DEMO_ROOT = ROOT
EXPECTED = {"events": 4026, "alerts": 10, "incidents": 1, "evidence": 26}


class DemoCommandError(ValueError):
    """Messages are deliberately fixed and never contain URLs or credentials."""


def demo_sqlite_path() -> Path:
    root = DEMO_ROOT.resolve()
    runtime = root / ".runtime"
    if runtime.resolve() != runtime:
        raise DemoCommandError("The reserved demo directory must not be a symlink.")
    target = runtime / "aegisgraph-demo.db"
    if target.resolve() != target or (target.exists() and target.stat().st_nlink > 1):
        raise DemoCommandError("The reserved demo database must not be a symlink.")
    return target


def demo_database_url(postgres_port: int | None = None) -> str:
    if postgres_port is not None:
        if not 1024 <= postgres_port <= 65535:
            raise DemoCommandError("The local demo PostgreSQL port must be between 1024 and 65535.")
        return f"postgresql+psycopg://aegisgraph:demo-local-only@127.0.0.1:{postgres_port}/aegisgraph_demo"
    path = demo_sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def validate_reset_target(database_url: str) -> None:
    """Legacy resets also require an exact reserved database, not mere loopback."""
    try:
        url = make_url(database_url)
        if url.drivername == "sqlite" and url.database and not url.query:
            root = DEMO_ROOT.resolve()
            runtime = root / ".runtime"
            if runtime.resolve() != runtime:
                raise DemoCommandError("The reserved demo directory must not be a symlink.")
            candidate = Path(url.database).absolute()
            allowed = {runtime / "aegisgraph-demo.db", runtime / "e2e.db"}
            if (
                candidate in allowed
                and candidate.resolve() == candidate
                and not (candidate.exists() and candidate.stat().st_nlink > 1)
            ):
                return
        if (
            url.drivername == "postgresql+psycopg"
            and url.host == "127.0.0.1"
            and url.database == "aegisgraph_demo"
            and url.username == "aegisgraph"
            and not url.query
            and 1024 <= (url.port or 5432) <= 65535
        ):
            return
    except DemoCommandError:
        raise
    except Exception:
        pass
    raise DemoCommandError(
        "Reset refused: only the reserved .runtime/aegisgraph-demo.db, .runtime/e2e.db, "
        "or localhost PostgreSQL aegisgraph_demo database can be reset. Use demo-reset."
    )


def child_environment(database_url: str, *, provider: str = "deterministic") -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "DATABASE_URL": database_url,
            "AI_PROVIDER": provider,
            "AEGISGRAPH_LOAD_ENV": "false",
            "ALLOW_REMOTE_DEMO": "false",
        }
    )
    if provider == "deterministic":
        environment.pop("OPENAI_API_KEY", None)
        environment.pop("OPENAI_MODEL", None)
    return environment


def reset_demo(postgres_port: int | None = None) -> dict:
    database_url = demo_database_url(postgres_port)
    validate_reset_target(database_url)
    environment = child_environment(database_url)
    operations = [
        ("migration reset", ["alembic", "downgrade", "base"]),
        ("migration apply", ["alembic", "upgrade", "head"]),
        ("deterministic seed", ["aegisgraph.cli", "seed"]),
        ("deterministic evaluation", ["aegisgraph.cli", "evaluate"]),
    ]
    results = {}
    for label, arguments in operations:
        try:
            process = subprocess.run(
                [sys.executable, "-m", *arguments],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DemoCommandError(
                f"Demo {label} could not complete; check local database availability."
            ) from exc
        if process.returncode:
            raise DemoCommandError(
                f"Demo {label} failed; check local database availability. No credential-bearing error output is displayed."
            )
        if label in {"deterministic seed", "deterministic evaluation"}:
            try:
                results[label] = json.loads(process.stdout)
            except (ValueError, TypeError) as exc:
                raise DemoCommandError(f"Demo {label} returned an unexpected result.") from exc
    seed = results["deterministic seed"]
    evaluation = results["deterministic evaluation"]
    return {
        "status": "ready",
        "disposable": True,
        "database": "postgresql:aegisgraph_demo" if postgres_port else "sqlite:reserved_demo",
        "events": seed["events"],
        "alerts": seed["alerts"],
        "incidents": seed["incidents"],
        "detections": seed["detections"],
        "evaluations": {
            "provider": "deterministic",
            "total": evaluation["total"],
            "passed": evaluation["passed"],
            "failed": evaluation["failed"],
        },
    }


def serve_demo(postgres_port: int | None, port: int, provider: str) -> int:
    if provider not in {"deterministic", "openai"} or not 1024 <= port <= 65535:
        raise DemoCommandError(
            "Choose a supported provider and an API port between 1024 and 65535."
        )
    database_url = demo_database_url(postgres_port)
    environment = child_environment(database_url, provider=provider)
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "aegisgraph.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    return process.returncode


def check_demo_health(api_url: str = "http://127.0.0.1:8000") -> dict:
    try:
        parsed = urlparse(api_url)
        port = parsed.port
    except ValueError as exc:
        raise DemoCommandError("Demo health requires a valid loopback HTTP API URL.") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise DemoCommandError(
            "Demo health requires a plain loopback HTTP API URL without credentials."
        )
    checks = []

    def record(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    case = None
    try:
        with httpx.Client(base_url=api_url.rstrip("/"), timeout=10, trust_env=False) as client:
            health = client.get("/health")
            record(
                "api_reachable", health.status_code == 200, "Loopback API health response checked."
            )
            record(
                "database_reachable",
                health.status_code == 200 and health.json().get("status") == "ok",
                "API health executes a database query.",
            )
            counts = client.get("/api/overview").raise_for_status().json()["counts"]
            record(
                "seeded_counts",
                all(counts.get(key) == EXPECTED[key] for key in ("events", "alerts", "incidents")),
                "Expected 4,026 events, 10 alerts, and one incident.",
            )
            queue = client.get("/api/incidents").raise_for_status().json()["items"]
            primary = next(
                (
                    item
                    for item in queue
                    if item["title"] == "Suspected compromise of Atlas engineer account"
                ),
                None,
            )
            record("primary_incident", primary is not None, "Primary synthetic scenario exists.")
            if primary:
                case = client.get(f"/api/incidents/{primary['id']}").raise_for_status().json()
                record(
                    "case_evidence",
                    len(case["evidence"]) == EXPECTED["evidence"]
                    and len(case["alerts"]) == EXPECTED["alerts"],
                    "Expected 26 case evidence items and 10 linked alerts.",
                )
            else:
                record("case_evidence", False, "Primary case unavailable.")
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, KeyError, TypeError):
        record(
            "api_database_snapshot",
            False,
            "Could not retrieve a complete local API/database snapshot.",
        )
    fixtures = ROOT / "tests/fixtures/ai_cases.json"
    record("evaluation_fixtures", fixtures.is_file(), "Deterministic evaluation fixtures exist.")
    if case:
        from .analyst import DeterministicProvider, analyze

        answer = analyze(
            "What most likely happened?",
            case["id"],
            case["evidence"][:50],
            allowed_incident_ids={case["id"]},
            provider=DeterministicProvider(),
        )
        record(
            "deterministic_analyst",
            answer["status"] == "answered" and bool(answer["findings"]),
            "Explicit deterministic provider returned validated findings; no external model call was made.",
        )
    else:
        record(
            "deterministic_analyst",
            False,
            "Cannot validate the deterministic provider without primary evidence.",
        )
    return {
        "status": "healthy" if all(item["passed"] for item in checks) else "unhealthy",
        "checks": checks,
        "live_provider_called": False,
    }
