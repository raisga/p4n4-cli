"""p4n4 secret -- secret management subcommands."""

from __future__ import annotations

import secrets
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from p4n4.utils import env as envutil
from p4n4.utils import manifest as mf

app = typer.Typer(help="Manage project secrets.")
console = Console()

_ROTATABLE_KEYS = [
    # IoT layer
    "INFLUXDB_PASSWORD",
    "INFLUXDB_TOKEN",
    "GRAFANA_PASSWORD",
    # AI layer
    "LETTA_SERVER_PASSWORD",
    "N8N_BASIC_AUTH_PASSWORD",
    "N8N_ENCRYPTION_KEY",
]


def _gen_secret(n: int = 32) -> str:
    return secrets.token_hex(n)


def _require_project() -> tuple[Path, Path]:
    manifest_path = mf.find()
    if manifest_path is None:
        console.print(
            "[red]Error:[/red] No [bold].p4n4.json[/bold] found. "
            "Not inside a p4n4 project directory."
        )
        raise typer.Exit(1)
    env_path = manifest_path.parent / ".env"
    if not env_path.exists():
        console.print("[red]Error:[/red] No [bold].env[/bold] file found in project directory.")
        raise typer.Exit(1)
    return manifest_path, env_path


@app.command("show")
def show() -> None:
    """Show masked secrets from .env."""
    _, env_path = _require_project()
    env = envutil.load(env_path)

    table = Table(title="Project secrets (.env)", show_header=True)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key in _ROTATABLE_KEYS:
        if key in env:
            val = env[key]
            masked = val[:4] + "*" * max(0, len(val) - 4) if len(val) > 4 else "****"
            table.add_row(key, masked)

    console.print(table)


@app.command("rotate")
def rotate() -> None:
    """Re-generate all password/token values in .env."""
    _, env_path = _require_project()
    env = envutil.load(env_path)
    new_values: dict[str, str] = {}

    for key in _ROTATABLE_KEYS:
        if key in env:
            new_values[key] = _gen_secret(16 if "PASSWORD" in key else 32)

    if not new_values:
        console.print("[yellow]No rotatable secrets found in .env.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Secrets to rotate", show_header=True)
    table.add_column("Key")
    table.add_column("New value")
    for k, v in new_values.items():
        table.add_row(k, v)
    console.print(table)

    confirmed = typer.confirm("\nRotate these secrets in .env?", default=True)
    if not confirmed:
        raise typer.Abort()

    updated = {**env, **new_values}
    envutil.write(env_path, updated)

    console.print("\n[green]✓[/green] Secrets rotated in [bold].env[/bold]")
    console.print(
        "[yellow]Remember to run [bold]p4n4 down && p4n4 up[/bold] "
        "to apply the new secrets.[/yellow]"
    )


@app.command("generate")
def generate() -> None:
    """Print new secret values to stdout without writing to disk."""
    table = Table(title="Generated secrets (not saved)", show_header=True)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key in _ROTATABLE_KEYS:
        value = _gen_secret(16 if "PASSWORD" in key else 32)
        table.add_row(key, value)

    console.print(table)
