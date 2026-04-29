"""Tests for gtm db CLI commands."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the DB at a temp directory so tests don't touch real data/."""
    monkeypatch.setenv("BASE_DIR", str(tmp_path))
    monkeypatch.setenv("MOCK_MODE", "true")
    # Reset lru_cache so settings re-read the patched env
    from src.config import settings as settings_mod
    settings_mod.get_settings.cache_clear()

    # Reset engine cache so it uses the new DB URL
    import src.db.session as session_mod
    session_mod._engine = None
    session_mod._session_factory = None

    yield

    session_mod._engine = None
    session_mod._session_factory = None
    settings_mod.get_settings.cache_clear()


def test_db_init_and_status(isolated_db: None) -> None:
    result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 0, result.output
    assert "initialised" in result.output.lower() or "applied" in result.output.lower()

    result = runner.invoke(app, ["db", "status"])
    assert result.exit_code == 0, result.output
    assert "companies" in result.output


def test_db_reset_requires_yes(isolated_db: None) -> None:
    runner.invoke(app, ["db", "init"])
    result = runner.invoke(app, ["db", "reset"])
    # Without --yes it should prompt/abort; typer testing doesn't provide stdin
    # so it should exit with abort
    assert result.exit_code != 0 or "Continue" in result.output


def test_db_reset_with_yes(isolated_db: None) -> None:
    runner.invoke(app, ["db", "init"])
    result = runner.invoke(app, ["db", "reset", "--yes"])
    assert result.exit_code == 0, result.output
