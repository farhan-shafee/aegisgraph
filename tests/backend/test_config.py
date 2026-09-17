import pytest
from aegisgraph.config import Settings, load_local_environment

PUBLIC_CONFIG = {
    "app_mode": "public_demo",
    "database_url": "postgresql://demo:fixture-password@database.example/demo",
    "allowed_origins": ("https://frontend.example",),
    "allowed_hosts": ("api.example", "healthcheck.railway.app"),
}


def test_dotenv_preserves_process_values_and_does_not_expand_values(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text(
        "AEGISGRAPH_TEST_FIRST=file-value\nAEGISGRAPH_TEST_SECOND=${AEGISGRAPH_TEST_FIRST}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AEGISGRAPH_LOAD_ENV", "true")
    monkeypatch.setenv("AEGISGRAPH_TEST_FIRST", "process-value")
    monkeypatch.delenv("AEGISGRAPH_TEST_SECOND", raising=False)
    load_local_environment(file)
    import os

    assert os.environ["AEGISGRAPH_TEST_FIRST"] == "process-value"
    assert os.environ["AEGISGRAPH_TEST_SECOND"] == "${AEGISGRAPH_TEST_FIRST}"
    monkeypatch.delenv("AEGISGRAPH_TEST_SECOND")


def test_dotenv_disabled_in_tests_and_database_credentials_not_in_repr(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text("AEGISGRAPH_TEST_DISABLED=not-loaded\n", encoding="utf-8")
    monkeypatch.setenv("AEGISGRAPH_LOAD_ENV", "false")
    monkeypatch.delenv("AEGISGRAPH_TEST_DISABLED", raising=False)
    load_local_environment(file)
    import os

    assert "AEGISGRAPH_TEST_DISABLED" not in os.environ
    assert "fixture-password" not in repr(
        Settings(database_url="postgresql://user:fixture-password@localhost/db")
    )


def test_public_demo_skips_local_dotenv_even_when_loading_is_enabled(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text("AEGISGRAPH_TEST_DISABLED=not-loaded\n", encoding="utf-8")
    monkeypatch.setenv("APP_MODE", "public_demo")
    monkeypatch.setenv("AEGISGRAPH_LOAD_ENV", "true")
    monkeypatch.delenv("AEGISGRAPH_TEST_DISABLED", raising=False)
    load_local_environment(file)
    import os

    assert "AEGISGRAPH_TEST_DISABLED" not in os.environ


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_public_config_normalizes_railway_postgres_without_exposing_credentials(scheme):
    config = Settings(
        **{
            **PUBLIC_CONFIG,
            "database_url": f"{scheme}://demo:fixture-password@database.example/demo",
        }
    )
    assert config.public_demo
    assert config.database_url.startswith("postgresql+psycopg://")
    assert "fixture-password" not in repr(config)


@pytest.mark.parametrize(
    "database_url",
    ["", "sqlite:///private-file.db", "postgresql:///demo", "mysql://user:secret@database/demo"],
)
def test_public_config_requires_explicit_postgres_database(database_url):
    with pytest.raises(ValueError, match="PostgreSQL DATABASE_URL") as error:
        Settings(**{**PUBLIC_CONFIG, "database_url": database_url})
    assert "secret" not in str(error.value)
    assert "private-file" not in str(error.value)


@pytest.mark.parametrize(
    "origins",
    [
        (),
        ("*",),
        ("http://frontend.example",),
        ("https://*.frontend.example",),
        ("https://user:secret@frontend.example",),
        ("https://frontend.example/path",),
        ("https://frontend.example?secret=value",),
        ("https://frontend.example#fragment",),
        ("https://frontend.example:invalid",),
        ("https://frontend.example:",),
    ],
)
def test_public_config_rejects_ambiguous_or_unsafe_origins(origins):
    with pytest.raises(ValueError, match="HTTPS ALLOWED_ORIGINS") as error:
        Settings(**{**PUBLIC_CONFIG, "allowed_origins": origins})
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "hosts",
    [
        (),
        ("*",),
        ("*.example",),
        ("https://api.example",),
        ("api.example/path",),
        ("user:secret@api.example",),
        ("api.example:443",),
    ],
)
def test_public_config_requires_explicit_hostnames(hosts):
    with pytest.raises(ValueError, match="hostname-only ALLOWED_HOSTS"):
        Settings(**{**PUBLIC_CONFIG, "allowed_hosts": hosts})


def test_public_config_allows_explicit_https_loopback_rehearsal():
    config = Settings(
        **{
            **PUBLIC_CONFIG,
            "allowed_origins": ("https://localhost:3443", "https://127.0.0.1:3443"),
            "allowed_hosts": ("localhost", "127.0.0.1"),
        }
    )
    assert config.public_demo


def test_app_mode_is_explicit_and_never_inferred_from_node_env(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")
    assert Settings().app_mode == "local"
    with pytest.raises(ValueError, match="APP_MODE must be local or public_demo"):
        Settings(app_mode="production")
