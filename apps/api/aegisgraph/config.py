import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


def load_local_environment(path: Path | None = None) -> None:
    """Load only the repository env file, preserving explicit process settings.

    Values never enter settings serialization or diagnostics. Interpolation is
    disabled so a literal secret cannot accidentally be expanded into another
    configuration field. Tests explicitly disable local file loading.
    """
    if os.getenv("AEGISGRAPH_LOAD_ENV", "true").lower() not in {"false", "0", "no"}:
        load_dotenv(dotenv_path=path or ROOT / ".env", override=False, interpolate=False)


load_local_environment()


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://aegisgraph:demo-local-only@127.0.0.1:5432/aegisgraph",
        ),
        repr=False,
    )
    demo_analyst: str = os.getenv("DEMO_ANALYST", "demo.analyst")
    allowed_origins: tuple[str, ...] = tuple(
        os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    )
    allow_remote_demo: bool = os.getenv("ALLOW_REMOTE_DEMO", "false").lower() == "true"


settings = Settings()
