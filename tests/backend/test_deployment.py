from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from aegisgraph import cli, deployment, services
from aegisgraph.db import Base
from aegisgraph.models import Audit, EvaluationRun, Evidence, Incident, Note, SecurityEvent
from aegisgraph.services import execute_evaluations, seed_database
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_dataset_readiness_requires_complete_seed_and_evaluations(db):
    assert deployment.dataset_status(db)["status"] == "empty"
    seed_database(db)
    assert not deployment.dataset_status(db)["ready"]
    execute_evaluations(db)
    before = db.scalar(select(Incident)).updated_at
    assert deployment.dataset_status(db)["ready"]
    assert deployment.dataset_status(db)["counts"] == deployment.EXPECTED_COUNTS
    assert db.scalar(select(Incident)).updated_at == before
    db.add(
        Note(
            id="private-note", incident_id=deployment.FLAGSHIP_ID, text="Local work", author="demo"
        )
    )
    db.commit()
    assert not deployment.dataset_status(db)["ready"]


def test_readiness_does_not_treat_unrelated_rows_as_empty(db):
    db.add(Incident(id="partial", title="Partial", summary="", severity="low"))
    db.commit()
    assert deployment.dataset_status(db)["status"] == "incomplete"


def test_readiness_rejects_local_case_edits_annotations_and_additional_audit(db):
    seed_database(db)
    execute_evaluations(db)
    assert deployment.dataset_status(db)["ready"]
    for model, field, value in (
        (Incident, "owner", "private-analyst"),
        (Incident, "status", "resolved"),
        (Incident, "severity", "low"),
        (Incident, "title", "Private title"),
        (Incident, "summary", "Private case summary"),
        (Evidence, "note", "Private annotation"),
        (Evidence, "relevance", "benign"),
    ):
        setattr(db.scalar(select(model).limit(1)), field, value)
        db.flush()
        status = deployment.dataset_status(db)
        assert not status["core_ready"], field
        assert not status["ready"], field
        db.rollback()
    db.add(
        Audit(
            id="extra-audit",
            incident_id=deployment.FLAGSHIP_ID,
            actor="private-analyst",
            actor_type="human",
            action="status_changed",
            object_id=deployment.FLAGSHIP_ID,
        )
    )
    db.flush()
    assert not deployment.dataset_status(db)["core_ready"]


def test_readiness_requires_exact_initialization_audit_metadata(db):
    seed_database(db)
    execute_evaluations(db)
    row = db.scalar(select(Audit).where(Audit.action == "incident_created"))
    row.after = {**row.after, "private-note": "not-part-of-fixture"}
    db.flush()
    assert not deployment.dataset_status(db)["ready"]


@pytest.fixture
def admin_database(db, monkeypatch):
    class Lock:
        granted = True

        def __init__(self):
            self.actions = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.actions.append("connection_closed")

        def scalar(self, statement, params):
            assert "pg_try_advisory_lock" in str(statement)
            assert params == {"key": deployment.INITIALIZATION_LOCK}
            self.actions.append("lock_attempted")
            return self.granted

        def execute(self, statement, params):
            assert "pg_advisory_unlock" in str(statement)
            assert params == {"key": deployment.INITIALIZATION_LOCK}
            self.actions.append("lock_released")

    lock = Lock()
    migrations = []
    monkeypatch.setattr(deployment, "require_public_mode", lambda: None)
    monkeypatch.setattr(deployment, "engine", SimpleNamespace(connect=lambda: lock))
    monkeypatch.setattr(deployment, "Session", lambda engine: nullcontext(db))
    monkeypatch.setattr(
        deployment.command, "upgrade", lambda config, revision: migrations.append(revision)
    )
    return SimpleNamespace(db=db, lock=lock, migrations=migrations)


def test_public_initialization_requires_explicit_seed_and_preserves_existing_data(
    admin_database, monkeypatch
):
    fixture = admin_database
    assert deployment.initialize_public()["status"] == "empty"
    assert not fixture.db.scalar(select(func.count()).select_from(SecurityEvent))
    assert deployment.initialize_public(seed=True)["action"] == "initialized"
    before_case_time = fixture.db.scalar(select(Incident)).updated_at
    before_audit_ids = set(fixture.db.scalars(select(Audit.id)))

    def forbidden(*args, **kwargs):
        pytest.fail("Initialization tried to seed or evaluate an existing ready dataset")

    monkeypatch.setattr(services, "seed_database", forbidden)
    monkeypatch.setattr(services, "execute_evaluations", forbidden)
    assert deployment.initialize_public(seed=True)["action"] == "unchanged"
    assert deployment.initialize_public()["action"] == "unchanged"
    assert fixture.db.scalar(select(Incident)).updated_at == before_case_time
    assert set(fixture.db.scalars(select(Audit.id))) == before_audit_ids
    assert fixture.migrations == ["head"] * 4
    assert fixture.lock.actions.count("lock_released") == 4


def test_public_initialization_refuses_partial_data_without_replacing_it(
    admin_database, monkeypatch
):
    fixture = admin_database
    fixture.db.add(Incident(id="unrelated", title="Private case", summary="", severity="low"))
    fixture.db.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Partial database must never be seeded or reset")

    monkeypatch.setattr(services, "seed_database", forbidden)
    monkeypatch.setattr(services, "execute_evaluations", forbidden)
    with pytest.raises(deployment.InitializationError, match="incomplete or non-demo"):
        deployment.initialize_public(seed=True)
    assert fixture.db.get(Incident, "unrelated").title == "Private case"
    assert not fixture.db.scalar(select(func.count()).select_from(SecurityEvent))
    assert fixture.lock.actions == ["lock_attempted", "lock_released", "connection_closed"]


def test_public_initialization_completes_only_missing_deterministic_evaluation(
    admin_database, monkeypatch
):
    fixture = admin_database
    seed_database(fixture.db)
    assert deployment.dataset_status(fixture.db)["core_ready"]

    def forbidden(*args, **kwargs):
        pytest.fail("Existing clean core data must not be reseeded")

    monkeypatch.setattr(services, "seed_database", forbidden)
    assert deployment.initialize_public(seed=True)["ready"]
    assert fixture.db.scalar(select(func.count()).select_from(EvaluationRun)) == 1
    assert fixture.lock.actions == ["lock_attempted", "lock_released", "connection_closed"]


def test_public_initialization_refuses_competing_lock_before_any_migration(admin_database):
    fixture = admin_database
    fixture.lock.granted = False
    with pytest.raises(deployment.InitializationError, match="Another public initialization"):
        deployment.initialize_public(seed=True)
    assert fixture.migrations == []
    assert fixture.lock.actions == ["lock_attempted", "connection_closed"]


@pytest.mark.parametrize("stage", ["migration", "seed", "evaluation"])
def test_public_initialization_releases_advisory_lock_after_failure(
    admin_database, monkeypatch, stage
):
    def failure(*args, **kwargs):
        raise RuntimeError("fixture failure")

    if stage == "migration":
        monkeypatch.setattr(deployment.command, "upgrade", failure)
    else:
        monkeypatch.setattr(
            services, "seed_database" if stage == "seed" else "execute_evaluations", failure
        )
    with pytest.raises(RuntimeError, match="fixture failure"):
        deployment.initialize_public(seed=True)
    assert admin_database.lock.actions == ["lock_attempted", "lock_released", "connection_closed"]


def test_public_initialization_fails_closed_when_evaluations_fail(admin_database, monkeypatch):
    monkeypatch.setattr(services, "execute_evaluations", lambda db: {"failed": 1})
    with pytest.raises(deployment.InitializationError, match="evaluations failed"):
        deployment.initialize_public(seed=True)
    assert not deployment.dataset_status(admin_database.db)["ready"]
    assert admin_database.lock.actions == ["lock_attempted", "lock_released", "connection_closed"]


@pytest.mark.parametrize("command", ["seed", "evaluate", "demo-reset", "demo-api"])
def test_public_mode_denies_local_administration(monkeypatch, command, capsys):
    monkeypatch.setattr(cli, "settings", SimpleNamespace(public_demo=True))
    monkeypatch.setattr("sys.argv", ["aegisgraph", command])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 2
    assert "Local demo commands are disabled" in capsys.readouterr().err


@pytest.mark.parametrize("port", [None, "", "not-a-port", "0", "65536"])
def test_public_serve_requires_platform_port(monkeypatch, port):
    monkeypatch.setattr(deployment, "require_public_mode", lambda: None)
    if port is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", port)
    with pytest.raises(deployment.InitializationError, match="PORT"):
        deployment.serve_public()


def test_public_serve_uses_one_worker_and_no_access_or_proxy_logs(monkeypatch):
    import uvicorn

    calls = []
    monkeypatch.setattr(deployment, "require_public_mode", lambda: None)
    monkeypatch.setenv("PORT", "8765")
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    deployment.serve_public()
    options = calls[0][1]
    assert options["port"] == 8765
    assert options["host"] == "0.0.0.0"
    assert options["workers"] == 1
    assert options["access_log"] is False
    assert options["proxy_headers"] is False


def test_public_admin_database_failures_never_print_connection_details(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aegisgraph", "public-check"])

    def fail():
        raise RuntimeError("private-connection-marker")

    monkeypatch.setattr(deployment, "check_public", fail)
    with pytest.raises(SystemExit):
        cli.main()
    captured = capsys.readouterr()
    assert "private-connection-marker" not in captured.out + captured.err
    assert "Public administration failed" in captured.err
