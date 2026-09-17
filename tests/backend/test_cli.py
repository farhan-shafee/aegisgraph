from contextlib import nullcontext

import pytest
from aegisgraph import cli


def test_evaluation_cli_failure_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aegisgraph", "evaluate"])
    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(None))
    monkeypatch.setattr(
        cli, "execute_evaluations", lambda _db: {"total": 2, "passed": 1, "failed": 1}
    )
    with pytest.raises(SystemExit) as failure:
        cli.main()
    assert failure.value.code == 1
    assert '"failed": 1' in capsys.readouterr().out


def test_evaluation_cli_success_reports_executed_count(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aegisgraph", "evaluate"])
    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(None))
    monkeypatch.setattr(
        cli, "execute_evaluations", lambda _db: {"total": 2, "passed": 2, "failed": 0}
    )
    cli.main()
    assert '"passed": 2' in capsys.readouterr().out
