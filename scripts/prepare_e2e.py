"""Prepare only the dedicated disposable browser-test database, never DATABASE_URL."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    database = runtime / "e2e.db"
    environment = dict(os.environ)
    environment["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    environment["AI_PROVIDER"] = "deterministic"
    environment["ALLOWED_ORIGINS"] = "http://127.0.0.1:3100,http://localhost:3100"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=environment,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "aegisgraph.cli", "seed", "--reset"],
        cwd=root,
        env=environment,
        check=True,
    )
    print(f"Isolated browser database ready: {database}")


if __name__ == "__main__":
    main()
