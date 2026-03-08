"""Shared pytest fixtures for p4n4-cli tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from p4n4.cli import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli():
    return app
