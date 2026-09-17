import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://aegisgraph:demo-local-only@127.0.0.1:5432/aegisgraph",
    )
    demo_analyst: str = os.getenv("DEMO_ANALYST", "demo.analyst")
    allowed_origins: tuple[str, ...] = tuple(
        os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    )
    allow_remote_demo: bool = os.getenv("ALLOW_REMOTE_DEMO", "false").lower() == "true"


settings = Settings()
