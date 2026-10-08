"""p4n4 secret -- secret management subcommands."""

from __future__ import annotations

from pathlib import Path

import typer
from p4n4_lib import env as envutil
from p4n4_lib import secrets as secretutil
from rich.console import Console
from rich.table import Table

from p4n4.project import require_compose_dirs

app = typer.Typer(help="Manage project secrets.")
console = Console()


def _require_env_files() -> list[tuple[str, Path]]:
    """Return (layer, .env path) pairs for every stack that has one."""
    files = [
        (name, path / envutil.ENV_FILE)
        for name, path in require_compose_dirs()
        if (path / envutil.ENV_FILE).exists()
    ]
    if not files:
        console.print("[red]Error:[/red] No [bold].env[/bold] file found in project directory.")
        raise typer.Exit(1)
    return files


@app.command("show")
def show() -> None:
    """Show masked secrets from .env, including external ones (never rotated)."""
    files = _require_env_files()
    multi = len(files) > 1

    table = Table(title="Project secrets (.env)", show_header=True)
    if multi:
        table.add_column("Stack", style="dim")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for name, env_path in files:
        env = envutil.load(env_path)
        row = [name] if multi else []
        for key in secretutil.SECRET_KEYS:
            if key in env:
                val = env[key]
                masked = val[:4] + "*" * max(0, len(val) - 4) if len(val) > 4 else "****"
                table.add_row(*row, key, masked)
        # Externally issued (e.g. an MQTT broker password): a human-chosen value
        # shows no characters, and an empty one (nothing configured) is skipped
        for key in secretutil.EXTERNAL_KEYS:
            if env.get(key):
                table.add_row(*row, key, "******** [dim](external, not rotated)[/dim]")

    console.print(table)


@app.command("rotate")
def rotate() -> None:
    """Re-generate the secrets in .env that services pick up at their next start."""
    files = _require_env_files()
    envs = [(name, path, envutil.load(path)) for name, path in files]

    # Services keep these from their first setup: a new value in .env alone
    # would lock clients out (InfluxDB, Grafana) or stop n8n from starting
    setup_only = [key for key in secretutil.SETUP_KEYS if any(key in env for _, _, env in envs)]
    if setup_only:
        console.print(
            "[dim]Not rotated, because their services keep the value from first setup: "
            f"{', '.join(setup_only)}. Change them in the service itself "
            "(see the Security guide: https://github.com/raisga/p4n4-docs/blob/main/guides/security.md#secret-rotation).[/dim]\n"
        )

    # One new value per key, shared across stacks so cross-stack keys
    # (e.g. INFLUXDB_TOKEN in both iot and ai) stay in sync
    new_values: dict[str, str] = {
        key: secretutil.rotation_value(key)
        for key in secretutil.ROTATABLE_KEYS
        if any(key in env for _, _, env in envs)
    }

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

    for _name, path, env in envs:
        updates = {k: v for k, v in new_values.items() if k in env}
        if updates:
            envutil.write(path, {**env, **updates})

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

    for key in secretutil.SECRET_KEYS:
        table.add_row(key, secretutil.rotation_value(key))

    console.print(table)
