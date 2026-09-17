import ipaddress
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]


def load_local_environment(path: Path | None = None) -> None:
    """Load only the repository env file, preserving explicit process settings.

    Values never enter settings serialization or diagnostics. Interpolation is
    disabled so a literal secret cannot accidentally be expanded into another
    configuration field. Tests explicitly disable local file loading.
    """
    if os.getenv("APP_MODE", "local").strip().lower() == "public_demo":
        return
    if os.getenv("AEGISGRAPH_LOAD_ENV", "true").lower() not in {"false", "0", "no"}:
        load_dotenv(dotenv_path=path or ROOT / ".env", override=False, interpolate=False)


load_local_environment()


@dataclass(frozen=True)
class Settings:
    app_mode: str = field(default_factory=lambda: os.getenv("APP_MODE", "local").strip().lower())
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", ""),
        repr=False,
    )
    demo_analyst: str = field(default_factory=lambda: os.getenv("DEMO_ANALYST", "demo.analyst"))
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            value.strip()
            for value in os.getenv(
                "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
            if value.strip()
        )
    )
    allowed_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            value.strip()
            for value in os.getenv(
                "ALLOWED_HOSTS",
                ""
                if os.getenv("APP_MODE", "local").strip().lower() == "public_demo"
                else "localhost,127.0.0.1,[::1],testserver",
            ).split(",")
            if value.strip()
        )
    )
    allow_remote_demo: bool = field(
        default_factory=lambda: os.getenv("ALLOW_REMOTE_DEMO", "false").lower() == "true"
    )

    @property
    def public_demo(self) -> bool:
        return self.app_mode == "public_demo"

    def __post_init__(self):
        if self.app_mode not in {"local", "public_demo"}:
            raise ValueError("APP_MODE must be local or public_demo")
        if not self.database_url:
            if self.public_demo:
                raise ValueError("Public demo requires an explicit PostgreSQL DATABASE_URL")
            object.__setattr__(
                self,
                "database_url",
                "postgresql+psycopg://aegisgraph:demo-local-only@127.0.0.1:5432/aegisgraph",
            )
        if not self.public_demo:
            return
        try:
            url = make_url(self.database_url)
            if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
                raise ValueError
            if not url.host or not url.database:
                raise ValueError
            # Railway supplies the standard PostgreSQL scheme; this project installs psycopg 3.
            object.__setattr__(
                self,
                "database_url",
                url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False),
            )
        except Exception:
            raise ValueError("Public demo requires a valid PostgreSQL DATABASE_URL") from None
        if not self.allowed_origins or len(self.allowed_origins) > 5:
            raise ValueError("Public demo requires explicit HTTPS ALLOWED_ORIGINS")
        for origin in self.allowed_origins:
            try:
                parsed = urlsplit(origin)
                host = parsed.hostname or ""
                authority = f"[{host}]" if ":" in host else host
                if parsed.port is not None:
                    authority += f":{parsed.port}"
                valid = (
                    parsed.scheme == "https"
                    and origin == f"https://{authority}"
                    and parsed.netloc == authority
                    and parsed.port != 0
                    and self._hostname(host)
                    and not (parsed.path or parsed.query or parsed.fragment)
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Public demo requires explicit HTTPS ALLOWED_ORIGINS")
        if (
            not self.allowed_hosts
            or len(self.allowed_hosts) > 5
            or not all(self._hostname(host) for host in self.allowed_hosts)
        ):
            raise ValueError("Public demo requires explicit hostname-only ALLOWED_HOSTS")

    @staticmethod
    def _hostname(value: str) -> bool:
        try:
            ipaddress.ip_address(value.strip("[]"))
            return True
        except ValueError:
            pass
        return bool(
            len(value) <= 253
            and re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value)
            and all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in value.split(".")
            )
        )


settings = Settings()
