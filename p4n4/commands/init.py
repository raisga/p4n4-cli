"""p4n4 init — interactive project scaffold wizard."""

from __future__ import annotations

import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from p4n4 import sources
from p4n4.utils import env as envutil
from p4n4.utils import manifest as mf

console = Console()

# Files/dirs to copy from the iot repo into the new project
_IOT_COPY = [
    "docker-compose.yml",
    "config",
    "scripts",
]

# Files/dirs to copy from the ai repo into the new project
_AI_COPY = [
    "docker-compose.yml",
    "config",
    "scripts",
]


def _token(n: int = 32) -> str:
    return secrets.token_hex(n)


def _ask(prompt: str, default: str) -> str:
    return questionary.text(prompt, default=default).ask() or default


def _ask_password(prompt: str, default: str) -> str:
    return questionary.password(prompt).ask() or default


def _fetch_source(repo_url: str, source: str | None, prefix: str) -> tuple[Path, str | None]:
    """
    Return a (Path, tmpdir_or_None) to a stack source directory.

    If `source` is a local path it is used directly; otherwise the repo is
    cloned at shallow depth into a temp dir that the caller must clean up.
    """
    if source:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise typer.BadParameter(f"--source path does not exist: {path}")
        return path, None

    tmp = tempfile.mkdtemp(prefix=prefix)
    console.print(f"  Cloning [bold]{repo_url}[/bold] …")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, tmp],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(
            f"git clone failed:\n{result.stderr.strip()}\n\n"
            f"Tip: use --source <path> to scaffold from a local checkout."
        )
    return Path(tmp), tmp


def _fetch_iot_source(source: str | None) -> tuple[Path, str | None]:
    return _fetch_source(sources.iot_repo_url, source, "p4n4-iot-")


def _fetch_ai_source(source: str | None) -> tuple[Path, str | None]:
    return _fetch_source(sources.ai_repo_url, source, "p4n4-ai-")


def _scaffold_layer(
    project_dir: Path,
    copy_list: list[str],
    env_values: dict[str, str],
    src: Path,
    tmpdir: str | None,
) -> None:
    try:
        for name in copy_list:
            s = src / name
            if not s.exists():
                raise FileNotFoundError(f"Expected '{name}' in source repo but it was not found.")
            d = project_dir / name
            if s.is_dir():
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        # Make shell scripts executable
        scripts_dir = project_dir / "scripts"
        if scripts_dir.is_dir():
            for script in scripts_dir.glob("*.sh"):
                script.chmod(script.stat().st_mode | 0o111)

        # Write .env — values override the .env.example template from the repo
        env_template = src / ".env.example"
        envutil.write(project_dir / ".env", env_values, template_path=env_template)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _scaffold_iot(project_dir: Path, env_values: dict[str, str], source: str | None) -> None:
    src, tmpdir = _fetch_iot_source(source)
    _scaffold_layer(project_dir, _IOT_COPY, env_values, src, tmpdir)


def _scaffold_ai(project_dir: Path, env_values: dict[str, str], source: str | None) -> None:
    src, tmpdir = _fetch_ai_source(source)
    _scaffold_layer(project_dir, _AI_COPY, env_values, src, tmpdir)


def cmd(
    project_name: Annotated[str, typer.Argument(help="Name of the new project directory.")],
    layer: Annotated[
        str,
        typer.Option("--layer", help="Layer(s) to enable: iot, ai, edge, all."),
    ] = "iot",
    no_interactive: Annotated[
        bool, typer.Option("--no-interactive", help="Skip wizard and use defaults.")
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source-iot",
            help="Local path to a p4n4-iot checkout (skips git clone; useful offline).",
        ),
    ] = None,
    ai_source: Annotated[
        str | None,
        typer.Option(
            "--source-ai",
            help="Local path to a p4n4-ai checkout (skips git clone; useful offline).",
        ),
    ] = None,
) -> None:
    """Scaffold a new P4N4 project."""
    project_dir = Path.cwd() / project_name

    if project_dir.exists():
        console.print(f"[red]Error:[/red] Directory '[bold]{project_name}[/bold]' already exists.")
        raise typer.Exit(1)

    layers = ["iot", "ai", "edge"] if layer == "all" else [l.strip() for l in layer.split(",")]

    console.print(
        Panel(
            f"[bold cyan]p4n4 init[/bold cyan] — scaffolding [bold]{project_name}[/bold]",
            expand=False,
        )
    )

    # ── Collect configuration ─────────────────────────────────────────────────
    if no_interactive:
        org = "ming"
        tz = "UTC"
        influx_password = _token(12)
        influx_token = _token(32)
        grafana_password = _token(12)
        letta_password = _token(12)
        n8n_password = _token(12)
        n8n_encryption_key = _token(16)
        n8n_host = "localhost"
    else:
        console.print("\n[dim]Press Enter to accept defaults.[/dim]\n")
        org = _ask("InfluxDB organisation", "ming")
        tz = _ask("Timezone (TZ database name)", "UTC")
        influx_password = _ask_password(
            "InfluxDB admin password (leave blank to auto-generate)",
            _token(12),
        )
        influx_token = _ask_password(
            "InfluxDB API token (leave blank to auto-generate)",
            _token(32),
        )
        grafana_password = _ask_password(
            "Grafana admin password (leave blank to auto-generate)",
            _token(12),
        )
        if "ai" in layers:
            console.print("\n[dim]GenAI stack configuration:[/dim]\n")
            letta_password = _ask_password(
                "Letta server password (leave blank to auto-generate)",
                _token(12),
            )
            n8n_password = _ask_password(
                "n8n admin password (leave blank to auto-generate)",
                _token(12),
            )
            n8n_encryption_key = _ask_password(
                "n8n encryption key (leave blank to auto-generate, must be 32+ chars)",
                _token(16),
            )
            n8n_host = _ask("n8n hostname (for webhooks)", "localhost")
        else:
            letta_password = _token(12)
            n8n_password = _token(12)
            n8n_encryption_key = _token(16)
            n8n_host = "localhost"

    iot_env_values: dict[str, str] = {
        "TZ": tz,
        "INFLUXDB_USERNAME": "admin",
        "INFLUXDB_PASSWORD": influx_password,
        "INFLUXDB_ORG": org,
        "INFLUXDB_TOKEN": influx_token,
        "INFLUXDB_BUCKET": "raw_telemetry",
        "INFLUXDB_BUCKET_PROCESSED": "processed_metrics",
        "INFLUXDB_BUCKET_AI_EVENTS": "ai_events",
        "INFLUXDB_BUCKET_HEALTH": "system_health",
        "INFLUXDB_SANDBOX_BUCKET": "sandbox",
        "INFLUXDB_SANDBOX_RETENTION": "30d",
        "GRAFANA_USER": "admin",
        "GRAFANA_PASSWORD": grafana_password,
    }

    ai_env_values: dict[str, str] = {
        "LETTA_SERVER_PASSWORD": letta_password,
        "N8N_BASIC_AUTH_USER": "admin",
        "N8N_BASIC_AUTH_PASSWORD": n8n_password,
        "N8N_ENCRYPTION_KEY": n8n_encryption_key,
        "N8N_HOST": n8n_host,
        # Shared InfluxDB values (must match p4n4-iot when used alongside it)
        "INFLUXDB_TOKEN": influx_token,
        "INFLUXDB_ORG": org,
        "INFLUXDB_BUCKET": "raw_telemetry",
    }

    # ── Create project directory and scaffold ─────────────────────────────────
    project_dir.mkdir(parents=True)

    try:
        if "iot" in layers:
            _scaffold_iot(project_dir, iot_env_values, source)

        if "ai" in layers:
            _scaffold_ai(project_dir, ai_env_values, ai_source)

        mf.save(project_dir / mf.MANIFEST_FILE, mf.create(project_name, layers))

    except Exception as exc:
        shutil.rmtree(project_dir, ignore_errors=True)
        console.print(f"[red]Scaffold failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(f"\n[green]✓[/green] Project created at [bold]{project_dir}[/bold]\n")
    console.print("  [dim]Files generated:[/dim]")
    for f in sorted(project_dir.rglob("*")):
        if f.is_file():
            console.print(f"    {f.relative_to(project_dir)}")

    console.print(
        f"\n[bold]Next steps:[/bold]\n"
        f"  cd {project_name}\n"
        f"  p4n4 up\n"
    )
