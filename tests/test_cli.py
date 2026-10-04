"""Tests: verify CLI behaviour for both IoT and AI layers."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from p4n4_lib import env as envutil
from typer.testing import CliRunner

from p4n4 import __version__
from p4n4.cli import app

runner = CliRunner()


@contextmanager
def _isolated_filesystem(temp_dir: Path | None = None) -> Iterator[Path]:
    """Run inside a fresh temp directory. Stands in for CliRunner.isolated_filesystem,
    which Typer 0.27's CliRunner no longer has."""
    cwd = os.getcwd()
    path = Path(tempfile.mkdtemp(dir=temp_dir))
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(cwd)
        shutil.rmtree(path, ignore_errors=True)


_REPO_ROOT = Path(__file__).parent.parent


def _stack_source(name: str) -> str:
    """Locate a local stack checkout: CI clones it as a sibling repo (p4n4-<name>);
    the monorepo has it as a submodule under stacks/<name>."""
    candidates = [
        _REPO_ROOT.parent / f"p4n4-{name}",
        _REPO_ROOT.parent.parent / "stacks" / name,
        # The dashboard is a client, not a stack: clients/dashboard in the monorepo
        _REPO_ROOT.parent / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


# Local checkouts used as --source-iot / --source-ai / --source-edge (avoids network calls)
_IOT_SOURCE = _stack_source("iot")
_AI_SOURCE = _stack_source("ai")
_EDGE_SOURCE = _stack_source("edge")
_DASHBOARD_SOURCE = _stack_source("dashboard")


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
            "--source-dashboard",
            _DASHBOARD_SOURCE,
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
    with _isolated_filesystem():
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


def test_init_iot_without_dashboard_keeps_grafana_unframeable(iot_project):
    assert envutil.load(iot_project / ".env")["GRAFANA_ALLOW_EMBEDDING"] == "false"


def test_init_iot_generates_node_red_password(iot_project):
    env = envutil.load(iot_project / ".env")
    assert env["NODE_RED_PASSWORD"] != "adminpassword"
    assert len(env["NODE_RED_PASSWORD"]) >= 24


def test_init_iot_scripts_are_executable(iot_project):
    for script in (iot_project / "scripts").glob("*.sh"):
        assert script.stat().st_mode & stat.S_IXUSR, f"Not executable: {script.name}"


def test_init_fails_if_directory_exists():
    with _isolated_filesystem():
        runner.invoke(app, ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE])
        result = runner.invoke(
            app, ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE]
        )
        assert result.exit_code != 0
        assert "already exists" in result.output


# ── p4n4 init: external MQTT broker ─────────────────────────────────────────


def test_init_iot_bridge_disabled_by_default(iot_project):
    env = envutil.load(iot_project / ".env")
    assert env["MQTT_REMOTE_HOST"] == ""
    assert (iot_project / "config/mosquitto/bridge.sh").is_file()


def test_init_mqtt_remote_writes_bridge_env(tmp_path):
    ca = tmp_path / "broker-ca.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\n")
    with _isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app,
            [
                "init",
                "proj",
                "--no-interactive",
                "--source-iot",
                _IOT_SOURCE,
                "--mqtt-remote",
                "broker.example.com:8883",
                "--mqtt-remote-user",
                "alice",
                "--mqtt-remote-topics",
                "sensors/#,factory/+/celsius",
                "--mqtt-remote-tls",
                "--mqtt-remote-ca",
                str(ca),
            ],
            # The password comes from the environment, as recommended
            env={"P4N4_MQTT_REMOTE_PASSWORD": "s3cr$t pa#ss"},
        )
        assert result.exit_code == 0, result.output
        env = envutil.load(Path("proj/.env"))
        assert env["MQTT_REMOTE_HOST"] == "broker.example.com"
        assert env["MQTT_REMOTE_PORT"] == "8883"
        assert env["MQTT_REMOTE_USER"] == "alice"
        assert env["MQTT_REMOTE_PASSWORD"] == "s3cr$t pa#ss"
        assert env["MQTT_REMOTE_TOPICS"] == "sensors/#,factory/+/celsius"
        assert env["MQTT_REMOTE_TLS"] == "true"
        assert env["MQTT_REMOTE_CA_FILE"] == "broker-ca.crt"
        assert Path("proj/config/mosquitto/certs/broker-ca.crt").is_file()
        # Quoted so Compose doesn't interpolate $t or cut at the #
        assert "MQTT_REMOTE_PASSWORD='s3cr$t pa#ss'" in Path("proj/.env").read_text()


def test_init_mqtt_remote_requires_iot_layer(tmp_path):
    with _isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app,
            ["init", "proj", "--layer", "ai", "--no-interactive", "--mqtt-remote", "broker"],
        )
        assert result.exit_code != 0
        assert "--mqtt-remote" in result.output
        assert not Path("proj").exists()


def test_init_mqtt_remote_rejects_bad_port(tmp_path):
    with _isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app,
            ["init", "proj", "--no-interactive", "--source-iot", _IOT_SOURCE]
            + ["--mqtt-remote", "broker:notaport"],
        )
        assert result.exit_code != 0
        assert not Path("proj").exists()


def test_secret_external_password_is_masked_and_never_rotated(iot_project):
    env_path = iot_project / ".env"
    envutil.write(env_path, {**envutil.load(env_path), "MQTT_REMOTE_PASSWORD": "hunter22"})

    shown = _run_in(iot_project, ["secret", "show"])
    assert shown.exit_code == 0, shown.output
    assert "MQTT_REMOTE_PASSWORD" in shown.output
    assert "hunt" not in shown.output

    rotated = _run_in(iot_project, ["secret", "rotate"], input="y\n")
    assert rotated.exit_code == 0, rotated.output
    assert envutil.load(env_path)["MQTT_REMOTE_PASSWORD"] == "hunter22"


# ── p4n4 init: AI ────────────────────────────────────────────────────────────


def test_init_ai_exits_cleanly():
    with _isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "proj-ai", "--layer", "ai", "--no-interactive", "--source-ai", _AI_SOURCE],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "proj-ai" in result.output


def test_init_ai_starts_only_ollama_by_default():
    with _isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "proj", "--layer", "iot,ai", "--no-interactive"]
            + ["--source-iot", _IOT_SOURCE, "--source-ai", _AI_SOURCE],
        )
        assert result.exit_code == 0, result.output
        assert envutil.load(Path("proj/ai/.env"))["COMPOSE_PROFILES"] == "ollama"
        # Letta and n8n secrets are still generated, so enabling them later just works
        env = envutil.load(Path("proj/ai/.env"))
        assert env["N8N_ENCRYPTION_KEY"] != "change-me-32-char-encryption-key"
        assert env["LETTA_SERVER_PASSWORD"] != "lettapassword"
        assert "ai/.env" in result.output
        assert "COMPOSE_PROFILES=ollama,letta,n8n" in result.output


def test_init_names_compose_projects_per_layer():
    """Each layer gets its own Compose project name, so two projects' volumes never mix."""
    with _isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "Green.House", "--layer", "iot,ai", "--no-interactive"]
            + ["--source-iot", _IOT_SOURCE, "--source-ai", _AI_SOURCE],
        )
        assert result.exit_code == 0, result.output
        for layer in ("iot", "ai"):
            env = envutil.load(Path(f"Green.House/{layer}/.env"))
            assert env["COMPOSE_PROJECT_NAME"] == f"green-house-{layer}"


def test_init_single_layer_compose_project_is_the_project(iot_project):
    assert envutil.load(iot_project / ".env")["COMPOSE_PROJECT_NAME"] == iot_project.name


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
    with _isolated_filesystem():
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
    with _isolated_filesystem():
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
    with _isolated_filesystem():
        result = runner.invoke(app, ["up"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_down_requires_manifest():
    with _isolated_filesystem():
        result = runner.invoke(app, ["down"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_status_requires_manifest():
    with _isolated_filesystem():
        result = runner.invoke(app, ["status"])
        assert result.exit_code != 0
        assert ".p4n4.json" in result.output


def test_logs_requires_manifest():
    with _isolated_filesystem():
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
    assert data["layers"] == ["iot", "ai", "edge", "dashboard"]


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


# ── p4n4 init: dashboard ──────────────────────────────────────────────────────


def test_init_all_includes_the_dashboard(all_project):
    data = json.loads((all_project / ".p4n4.json").read_text())
    assert data["layers"][-1] == "dashboard"
    assert (all_project / "dashboard" / "docker-compose.yml").exists()
    env = envutil.load(all_project / "dashboard" / ".env")
    assert env["DASHBOARD_PORT"] == "8088"
    assert env["DASHBOARD_VERSION"]
    # Only the compose file is copied, not the Flutter sources
    assert sorted(p.name for p in (all_project / "dashboard").iterdir()) == [
        ".env",
        "docker-compose.yml",
    ]


def test_init_dashboard_with_iot(tmp_path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app,
            [
                "init",
                "proj-ui",
                "--layer",
                "iot,dashboard",
                "--no-interactive",
                "--source-iot",
                _IOT_SOURCE,
                "--source-dashboard",
                _DASHBOARD_SOURCE,
            ],
        )
        assert result.exit_code == 0, result.output
        validate = _run_in(tmp_path / "proj-ui", ["validate"])
        assert validate.exit_code == 0, validate.output
        iot_env = envutil.load(tmp_path / "proj-ui" / "iot" / ".env")
        assert iot_env["GRAFANA_ALLOW_EMBEDDING"] == "true"
    finally:
        os.chdir(old_cwd)


def test_dashboard_url_reads_the_layer_env(tmp_path):
    from p4n4.commands.lifecycle import dashboard_url

    assert dashboard_url(tmp_path) == "http://localhost:8088"
    envutil.write(tmp_path / ".env", {"DASHBOARD_PORT": "9000", "DASHBOARD_BIND": "192.168.1.20"})
    assert dashboard_url(tmp_path) == "http://192.168.1.20:9000"


def test_init_wizard_asks_for_external_broker(tmp_path, monkeypatch):
    from p4n4.commands import init as init_cmd

    ca = tmp_path / "ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\n")
    # Answers in prompt order; the empty ones accept defaults/auto-generate
    answers = iter(
        [
            "",  # InfluxDB organisation
            "",  # Timezone
            "",  # InfluxDB password
            "",  # InfluxDB token
            "",  # Grafana password
            "",  # Node-RED password
            True,  # Pull topics from an external broker?
            "mqtt.example.org",
            "bob",
            "pa'ss$",
            "",  # topics: default
            "remote/",
            True,  # TLS
            str(ca),
        ]
    )

    class _Prompt:
        def __init__(self, *_args, **_kwargs):
            self.answer = next(answers)

        def ask(self):
            return self.answer

    for name in ("text", "password", "confirm"):
        monkeypatch.setattr(init_cmd.questionary, name, _Prompt)

    with _isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "proj", "--source-iot", _IOT_SOURCE])
        assert result.exit_code == 0, result.output
        env = envutil.load(Path("proj/.env"))
        assert env["MQTT_REMOTE_HOST"] == "mqtt.example.org"
        assert env["MQTT_REMOTE_PORT"] == ""
        assert env["MQTT_REMOTE_USER"] == "bob"
        assert env["MQTT_REMOTE_PASSWORD"] == "pa'ss$"
        assert env["MQTT_REMOTE_TOPICS"] == "sensors/#"
        assert env["MQTT_REMOTE_PREFIX"] == "remote/"
        assert env["MQTT_REMOTE_TLS"] == "true"
        assert env["MQTT_REMOTE_CA_FILE"] == "ca.pem"
        assert Path("proj/config/mosquitto/certs/ca.pem").is_file()
    assert next(answers, None) is None, "wizard asked fewer questions than expected"
