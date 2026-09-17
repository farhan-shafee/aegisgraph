import os
import subprocess
import sys

import pytest
from aegisgraph.config import ROOT
from aegisgraph.db import make_engine
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError


def test_clean_sqlite_migrations_seed_and_database_immutability(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    env = {**os.environ, "DATABASE_URL": url}
    migrate = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert migrate.returncode == 0, migrate.stderr
    seed = subprocess.run(
        [sys.executable, "-m", "aegisgraph.cli", "seed"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert seed.returncode == 0, seed.stderr
    engine = make_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM events")) == 4026
        assert connection.scalar(text("SELECT COUNT(*) FROM incidents")) == 1
    for statement in (
        "UPDATE events SET source='atlas'",
        "DELETE FROM events",
        "UPDATE audit_log SET actor='tampered'",
        "DELETE FROM audit_log",
    ):
        with engine.begin() as connection:
            with pytest.raises(DatabaseError, match="append-only"):
                connection.execute(text(statement))
    engine.dispose()
    reset = subprocess.run(
        [sys.executable, "-m", "aegisgraph.cli", "seed", "--reset"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert reset.returncode != 0
    assert "Reset refused" in reset.stderr
    with make_engine(url).connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM events")) == 4026
