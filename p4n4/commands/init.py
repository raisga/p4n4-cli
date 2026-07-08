"""p4n4 init: interactive project scaffold wizard."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import questionary
import typer
from p4n4_lib import layout, scaffold
from p4n4_lib import manifest as mf
from p4n4_lib import secrets as secretutil
from p4n4_lib.layers import LAYERS
from rich.console import Console
from rich.panel import Panel

console = Console()


def _ask(prompt: str, default: str) -> str:
    return questionary.text(prompt, default=default).ask() or default


def _ask_password(prompt: str, default: str) -> str:
    return questionary.password(prompt).ask() or default


def _scaffold(
    project_dir: Path,
    layers: list[str],
    layer_name: str,
    env_values: dict[str, str],
    source: str | None,
) -> None:
    """Scaffold one layer into its layout directory (project root, or a
    per-layer subdirectory for multi-layer projects)."""
    layer = LAYERS[layer_name]
    dest = layout.layer_dir(project_dir, layers, layer_name)
    dest.mkdir(parents=True, exist_ok=True)
    if source is None:
        console.print(f"  Cloning [bold]{layer.repo_url}[/bold] …")
    scaffold.scaffold_layer(dest, layer, env_values, source=source)


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

    layers = ["iot", "ai", "edge"] if layer == "all" else [lyr.strip() for lyr in layer.split(",")]

    console.print(
        Panel(
            f"[bold cyan]p4n4 init[/bold cyan]: scaffolding [bold]{project_name}[/bold]",
            expand=False,
        )
    )

    # ── Collect configuration ─────────────────────────────────────────────────
    if no_interactive:
        org = "ming"
        tz = "UTC"
        influx_password = secretutil.token(12)
        influx_token = secretutil.token(32)
        grafana_password = secretutil.token(12)
        letta_password = secretutil.token(12)
        n8n_password = secretutil.token(12)
        n8n_encryption_key = secretutil.token(16)
        n8n_host = "localhost"
    else:
        console.print("\n[dim]Press Enter to accept defaults.[/dim]\n")
        org = _ask("InfluxDB organisation", "ming")
        tz = _ask("Timezone (TZ database name)", "UTC")
        influx_password = _ask_password(
            "InfluxDB admin password (leave blank to auto-generate)",
            secretutil.token(12),
        )
        influx_token = _ask_password(
            "InfluxDB API token (leave blank to auto-generate)",
            secretutil.token(32),
        )
        grafana_password = _ask_password(
            "Grafana admin password (leave blank to auto-generate)",
            secretutil.token(12),
        )
        if "ai" in layers:
            console.print("\n[dim]GenAI stack configuration:[/dim]\n")
            letta_password = _ask_password(
                "Letta server password (leave blank to auto-generate)",
                secretutil.token(12),
            )
            n8n_password = _ask_password(
                "n8n admin password (leave blank to auto-generate)",
                secretutil.token(12),
            )
            n8n_encryption_key = _ask_password(
                "n8n encryption key (leave blank to auto-generate, must be 32+ chars)",
                secretutil.token(16),
            )
            n8n_host = _ask("n8n hostname (for webhooks)", "localhost")
        else:
            letta_password = secretutil.token(12)
            n8n_password = secretutil.token(12)
            n8n_encryption_key = secretutil.token(16)
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
            _scaffold(project_dir, layers, "iot", iot_env_values, source)

        if "ai" in layers:
            _scaffold(project_dir, layers, "ai", ai_env_values, ai_source)

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

    console.print(f"\n[bold]Next steps:[/bold]\n  cd {project_name}\n  p4n4 up\n")
