from aegisgraph.config import Settings, load_local_environment


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
