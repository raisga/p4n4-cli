"""Smoke tests — verify the CLI is importable and basic invocations work."""

from __future__ import annotations

from typer.testing import CliRunner

from p4n4 import __version__
from p4n4.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "p4n4" in result.output


def test_init_stub():
    result = runner.invoke(app, ["init", "my-project"])
    assert "not yet implemented" in result.output


def test_up_stub():
    result = runner.invoke(app, ["up"])
    assert "not yet implemented" in result.output


def test_status_stub():
    result = runner.invoke(app, ["status"])
    assert "not yet implemented" in result.output
