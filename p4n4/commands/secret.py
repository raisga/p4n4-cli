"""p4n4 secret — secret generation and rotation."""

from __future__ import annotations

import secrets

import typer
from rich.console import Console
from rich.table import Table

from p4n4.utils import env as envutil
from p4n4.utils import manifest as mf

console = Console()

_ROTATABLE_KEYS = [
    "INFLUXDB_PASSWORD",
    "INFLUXDB_TOKEN",
    "GRAFANA_PASSWORD",
]


def _gen_secret(n: int = 32) -> str:
    return secrets.token_hex(n)


def cmd() -> None:
    """Generate or rotate project secrets."""
    manifest_path = mf.find()
    if manifest_path is None:
        console.print(
            "[red]Error:[/red] No [bold].p4n4.json[/bold] found. "
            "Not inside a p4n4 project directory."
        )
        raise typer.Exit(1)

    project_dir = manifest_path.parent
    env_path = project_dir / ".env"

    if not env_path.exists():
        console.print("[red]Error:[/red] No [bold].env[/bold] file found in project directory.")
        raise typer.Exit(1)

    env = envutil.load(env_path)
    new_values: dict[str, str] = {}

    for key in _ROTATABLE_KEYS:
        if key in env:
            new_values[key] = _gen_secret(16 if "PASSWORD" in key else 32)

    if not new_values:
        console.print("[yellow]No rotatable secrets found in .env.[/yellow]")
        raise typer.Exit(0)

    # Show what will be rotated and confirm
    table = Table(title="Secrets to rotate", show_header=True)
    table.add_column("Key")
    table.add_column("New value")
    for k, v in new_values.items():
        table.add_row(k, v)
    console.print(table)

    confirmed = typer.confirm("\nRotate these secrets in .env?", default=True)
    if not confirmed:
        raise typer.Abort()

    # Merge new values into existing env and rewrite
    updated = {**env, **new_values}
    envutil.write(env_path, updated)

    console.print("\n[green]✓[/green] Secrets rotated in [bold].env[/bold]")
    console.print(
        "[yellow]Remember to run [bold]p4n4 down && p4n4 up[/bold] "
        "to apply the new secrets.[/yellow]"
    )
