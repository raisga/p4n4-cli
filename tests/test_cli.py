"""Smoke tests — verify the CLI is importable and basic invocations work."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from p4n4 import __version__
from p4n4.cli import app

runner = CliRunner()

# Local p4n4-iot checkout used as --source in tests (avoids network calls)
_IOT_SOURCE = str(Path(__file__).parent.parent.parent / "p4n4-iot")


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "p4n4" in result.output


def test_init_no_interactive():
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "test-project", "--no-interactive", "--source", _IOT_SOURCE],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "test-project" in result.output


def test_up_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["up"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_status_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["status"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_validate_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["validate"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_validate_passes_on_fresh_project():
    with runner.isolated_filesystem() as tmpdir:
        runner.invoke(
            app,
            ["init", "proj", "--no-interactive", "--source", _IOT_SOURCE],
        )
        old_cwd = os.getcwd()
        os.chdir(Path(tmpdir) / "proj")
        try:
            result = runner.invoke(app, ["validate"], catch_exceptions=False)
        finally:
            os.chdir(old_cwd)
        assert result.exit_code == 0, result.output
        assert "All checks passed" in result.output


def test_secret_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["secret"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output
