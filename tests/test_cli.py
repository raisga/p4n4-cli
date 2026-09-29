"""Tests: verify CLI behaviour for both IoT and AI layers."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from p4n4_lib import env as envutil
from typer.testing import CliRunner

from p4n4 import __version__
from p4n4.cli import app

runner = CliRunner()

_REPO_ROOT = Path(__file__).parent.parent


def _stack_source(name: str) -> str:
    """Locate a local stack checkout: CI clones it as a sibling repo (p4n4-<name>);
    the monorepo has it as a submodule under stacks/<name>."""
    candidates = [
        _REPO_ROOT.parent / f"p4n4-{name}",
        _REPO_ROOT.parent.parent / "stacks" / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


# Local checkouts used as --source-iot / --source-ai / --source-edge (avoids network calls)
_IOT_SOURCE = _stack_source("iot")
_AI_SOURCE = _stack_source("ai")
_EDGE_SOURCE = _stack_source("edge")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def iot_project(tmp_path):
    """Scaffold a fresh IoT project and return its directory."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    runner.invoke(
        app,
        ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE],
    )
    yield tmp_path / "proj"
    os.chdir(old_cwd)


@pytest.fixture()
def ai_project(tmp_path):
    """Scaffold a fresh AI project and return its directory."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    runner.invoke(
        app,
        ["init", "proj-ai", "--layer", "ai", "--no-interactive", "--source-ai", _AI_SOURCE],
    )
    yield tmp_path / "proj-ai"
    os.chdir(old_cwd)


@pytest.fixture()
def multi_project(tmp_path):
    """Scaffold a fresh iot+ai project and return its directory."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    runner.invoke(
        app,
        [
            "init",
            "proj-multi",
            "--layer",
            "iot,ai",
            "--no-interactive",
            "--source-iot",
            _IOT_SOURCE,
            "--source-ai",
            _AI_SOURCE,
        ],
    )
    yield tmp_path / "proj-multi"
    os.chdir(old_cwd)


@pytest.fixture()
def all_project(tmp_path):
    """Scaffold a fresh project with every layer and return its directory."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "init",
            "proj-all",
            "--layer",
            "all",
            "--no-interactive",
            "--source-iot",
            _IOT_SOURCE,
            "--source-ai",
            _AI_SOURCE,
            "--source-edge",
            _EDGE_SOURCE,
        ],
    )
    assert result.exit_code == 0, result.output
    yield tmp_path / "proj-all"
    os.chdir(old_cwd)


def _run_in(project_dir, args, **kwargs):
    old_cwd = os.getcwd()
    os.chdir(project_dir)
    try:
        return runner.invoke(app, args, **kwargs)
    finally:
        os.chdir(old_cwd)


# ── Basic CLI ─────────────────────────────────────────────────────────────────


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "p4n4" in result.output


# ── p4n4 init: IoT ───────────────────────────────────────────────────────────


def test_init_iot_exits_cleanly():
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "proj" in result.output


def test_init_iot_creates_expected_files(iot_project):
    expected = [
        "docker-compose.yml",
        ".env",
        ".p4n4.json",
        "config/mosquitto/mosquitto.conf",
        "config/node-red/settings.js",
        "config/node-red/flows/flows.json",
        "config/grafana/provisioning/datasources/datasources.yml",
        "scripts/init-buckets.sh",
    ]
    for rel in expected:
        assert (iot_project / rel).exists(), f"Missing: {rel}"


def test_init_iot_manifest_content(iot_project):
    data = json.loads((iot_project / ".p4n4.json").read_text())
    assert data["schema_version"] == 1
    assert data["project"] == "proj"
    assert "iot" in data["layers"]


def test_init_iot_env_has_required_keys(iot_project):
    env = envutil.load(iot_project / ".env")
    for key in (
        "TZ",
        "INFLUXDB_USERNAME",
        "INFLUXDB_PASSWORD",
        "INFLUXDB_ORG",
        "INFLUXDB_TOKEN",
        "INFLUXDB_BUCKET",
        "GRAFANA_USER",
        "GRAFANA_PASSWORD",
        "NODE_RED_USER",
        "NODE_RED_PASSWORD",
    ):
        assert env.get(key), f".env missing key: {key}"


def test_init_iot_generates_node_red_password(iot_project):
    env = envutil.load(iot_project / ".env")
    assert env["NODE_RED_PASSWORD"] != "adminpassword"
    assert len(env["NODE_RED_PASSWORD"]) >= 24


def test_init_iot_scripts_are_executable(iot_project):
    for script in (iot_project / "scripts").glob("*.sh"):
        assert script.stat().st_mode & stat.S_IXUSR, f"Not executable: {script.name}"


def test_init_fails_if_directory_exists():
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE])
        result = runner.invoke(
            app, ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE]
        )
        assert result.exit_code != 0
        assert "already exists" in result.output


# ── p4n4 init: AI ────────────────────────────────────────────────────────────


def test_init_ai_exits_cleanly():
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "proj-ai", "--layer", "ai", "--no-interactive", "--source-ai", _AI_SOURCE],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "proj-ai" in result.output


def test_init_ai_creates_expected_files(ai_project):
    expected = [
        "docker-compose.yml",
        ".env",
        ".p4n4.json",
        "config/letta/letta.conf",
        "scripts/pull-models.sh",
    ]
    for rel in expected:
        assert (ai_project / rel).exists(), f"Missing: {rel}"


def test_init_ai_manifest_content(ai_project):
    data = json.loads((ai_project / ".p4n4.json").read_text())
    assert data["schema_version"] == 1
    assert data["project"] == "proj-ai"
    assert "ai" in data["layers"]
    assert "iot" not in data["layers"]


def test_init_ai_env_has_required_keys(ai_project):
    env = envutil.load(ai_project / ".env")
    for key in (
        "LETTA_SERVER_PASSWORD",
        "N8N_BASIC_AUTH_USER",
        "N8N_BASIC_AUTH_PASSWORD",
        "N8N_ENCRYPTION_KEY",
        "N8N_HOST",
        "INFLUXDB_TOKEN",
        "INFLUXDB_ORG",
        "INFLUXDB_BUCKET",
    ):
        assert env.get(key), f".env missing key: {key}"


def test_init_ai_scripts_are_executable(ai_project):
    for script in (ai_project / "scripts").glob("*.sh"):
        assert script.stat().st_mode & stat.S_IXUSR, f"Not executable: {script.name}"


# ── p4n4 init: multi-layer ───────────────────────────────────────────────────


def test_init_multi_layer_uses_per_layer_subdirs(multi_project):
    assert (multi_project / ".p4n4.json").exists()
    assert not (multi_project / "docker-compose.yml").exists()
    for rel in (
        "iot/docker-compose.yml",
        "iot/.env",
        "iot/config/mosquitto/mosquitto.conf",
        "iot/scripts/init-buckets.sh",
        "ai/docker-compose.yml",
        "ai/.env",
        "ai/config/letta/letta.conf",
        "ai/scripts/pull-models.sh",
    ):
        assert (multi_project / rel).exists(), f"Missing: {rel}"


def test_init_multi_layer_manifest_content(multi_project):
    data = json.loads((multi_project / ".p4n4.json").read_text())
    assert data["layers"] == ["iot", "ai"]


def test_init_multi_layer_shares_influxdb_values(multi_project):
    iot_env = envutil.load(multi_project / "iot" / ".env")
    ai_env = envutil.load(multi_project / "ai" / ".env")
    assert iot_env["INFLUXDB_TOKEN"] == ai_env["INFLUXDB_TOKEN"]
    assert iot_env["INFLUXDB_ORG"] == ai_env["INFLUXDB_ORG"]


def test_validate_passes_on_multi_layer_project(multi_project):
    old_cwd = os.getcwd()
    os.chdir(multi_project)
    try:
        result = runner.invoke(app, ["validate"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    assert "All checks passed" in result.output


def test_secret_rotate_multi_layer_keeps_shared_keys_in_sync(multi_project):
    old_cwd = os.getcwd()
    os.chdir(multi_project)
    try:
        result = runner.invoke(app, ["secret", "rotate"], input="y\n", catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    iot_env = envutil.load(multi_project / "iot" / ".env")
    ai_env = envutil.load(multi_project / "ai" / ".env")
    assert iot_env["INFLUXDB_TOKEN"] == ai_env["INFLUXDB_TOKEN"]
    assert ai_env["LETTA_SERVER_PASSWORD"]


def test_logs_multi_layer_requires_stack_to_follow(multi_project):
    old_cwd = os.getcwd()
    os.chdir(multi_project)
    try:
        result = runner.invoke(app, ["logs"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code != 0
    assert "--stack" in result.output


def test_up_unknown_stack_errors(multi_project):
    old_cwd = os.getcwd()
    os.chdir(multi_project)
    try:
        result = runner.invoke(app, ["up", "nope"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code != 0
    assert "not found" in result.output


# ── p4n4 validate ─────────────────────────────────────────────────────────────


def test_validate_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["validate"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_validate_passes_on_fresh_iot_project(iot_project):
    old_cwd = os.getcwd()
    os.chdir(iot_project)
    try:
        result = runner.invoke(app, ["validate"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    assert "All checks passed" in result.output


def test_validate_passes_on_fresh_ai_project(ai_project):
    old_cwd = os.getcwd()
    os.chdir(ai_project)
    try:
        result = runner.invoke(app, ["validate"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    assert "All checks passed" in result.output


def test_validate_fails_on_missing_required_file(iot_project):
    (iot_project / "config" / "mosquitto" / "mosquitto.conf").unlink()
    old_cwd = os.getcwd()
    os.chdir(iot_project)
    try:
        result = runner.invoke(app, ["validate"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code != 0
    assert "mosquitto.conf" in result.output


def test_validate_fails_on_missing_env_key(iot_project):
    env_path = iot_project / ".env"
    env = envutil.load(env_path)
    del env["GRAFANA_PASSWORD"]
    envutil.write(env_path, env)
    old_cwd = os.getcwd()
    os.chdir(iot_project)
    try:
        result = runner.invoke(app, ["validate"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code != 0
    assert "GRAFANA_PASSWORD" in result.output


# ── p4n4 secret ───────────────────────────────────────────────────────────────


def test_secret_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["secret", "rotate"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_secret_rotates_iot_secrets(iot_project):
    env_before = envutil.load(iot_project / ".env")
    old_cwd = os.getcwd()
    os.chdir(iot_project)
    try:
        result = runner.invoke(app, ["secret", "rotate"], input="y\n", catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    env_after = envutil.load(iot_project / ".env")
    for key in ("INFLUXDB_PASSWORD", "INFLUXDB_TOKEN", "GRAFANA_PASSWORD", "NODE_RED_PASSWORD"):
        assert env_after[key] != env_before[key], f"{key} was not rotated"


def test_secret_rotates_ai_secrets(ai_project):
    env_before = envutil.load(ai_project / ".env")
    old_cwd = os.getcwd()
    os.chdir(ai_project)
    try:
        result = runner.invoke(app, ["secret", "rotate"], input="y\n", catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    env_after = envutil.load(ai_project / ".env")
    for key in ("LETTA_SERVER_PASSWORD", "N8N_BASIC_AUTH_PASSWORD", "N8N_ENCRYPTION_KEY"):
        assert env_after[key] != env_before[key], f"{key} was not rotated"


# ── Stack lifecycle (require manifest) ────────────────────────────────────────


def test_up_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["up"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_down_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["down"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_status_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["status"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_logs_requires_manifest():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["logs"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


# ── p4n4 init: edge ──────────────────────────────────────────────────────────


def test_init_all_scaffolds_edge(all_project):
    for rel in (
        "edge/docker-compose.yml",
        "edge/.env",
        "edge/runner/Dockerfile",
        "edge/runner/runner.py",
        "edge/edge-impulse/models",
        "edge/onnx/models",
    ):
        assert (all_project / rel).exists(), f"Missing: {rel}"
    assert not list((all_project / "edge").rglob("__pycache__"))


def test_init_all_manifest_lists_every_layer(all_project):
    data = json.loads((all_project / ".p4n4.json").read_text())
    assert data["layers"] == ["iot", "ai", "edge"]


def test_init_all_edge_shares_influxdb_values(all_project):
    iot_env = envutil.load(all_project / "iot" / ".env")
    edge_env = envutil.load(all_project / "edge" / ".env")
    assert iot_env["INFLUXDB_TOKEN"] == edge_env["INFLUXDB_TOKEN"]
    assert iot_env["INFLUXDB_ORG"] == edge_env["INFLUXDB_ORG"]
    assert iot_env["TZ"] == edge_env["TZ"]


def test_validate_passes_on_all_layer_project(all_project):
    result = _run_in(all_project, ["validate"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "edge/runner/runner.py" in result.output


def test_validate_fails_on_missing_edge_file(all_project):
    (all_project / "edge" / "runner" / "runner.py").unlink()
    result = _run_in(all_project, ["validate"])
    assert result.exit_code != 0
    assert "edge/runner/runner.py" in result.output


def test_secret_rotate_keeps_edge_token_in_sync(all_project):
    result = _run_in(all_project, ["secret", "rotate"], input="y\n", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    iot_env = envutil.load(all_project / "iot" / ".env")
    edge_env = envutil.load(all_project / "edge" / ".env")
    assert iot_env["INFLUXDB_TOKEN"] == edge_env["INFLUXDB_TOKEN"]


def test_init_edge_only_validates(tmp_path):
    result = _run_in(
        tmp_path,
        ["init", "proj-edge", "--layer", "edge", "--no-interactive", "--source-edge", _EDGE_SOURCE],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "proj-edge" / "runner" / "runner.py").exists()
    result = _run_in(tmp_path / "proj-edge", ["validate"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_init_unknown_layer_errors(tmp_path):
    result = _run_in(tmp_path, ["init", "proj-bad", "--layer", "iot,nope", "--no-interactive"])
    assert result.exit_code != 0
    assert "nope" in result.output
    assert not (tmp_path / "proj-bad").exists()
