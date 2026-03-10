"""p4n4 up / down / status / logs — stack lifecycle commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from p4n4.utils import compose
from p4n4.utils import manifest as mf

console = Console()


def _project_dir() -> "Path":
    from pathlib import Path

    manifest_path = mf.find()
    if manifest_path is None:
        console.print(
            "[red]Error:[/red] No [bold].p4n4.json[/bold] found. "
            "Run [bold]p4n4 init <name>[/bold] first, or cd into a project directory."
        )
        raise typer.Exit(1)
    return manifest_path.parent


def up(
    edge: Annotated[bool, typer.Option("--edge", help="Start Edge AI services only.")] = False,
    ai: Annotated[bool, typer.Option("--ai", help="Start Gen AI services only.")] = False,
    build: Annotated[bool, typer.Option("--build", help="Rebuild images before starting.")] = False,
    pull: Annotated[bool, typer.Option("--pull", help="Pull latest images before starting.")] = False,
) -> None:
    """Start the project stack."""
    cwd = _project_dir()
    console.print(f"[cyan]Starting stack in[/cyan] [bold]{cwd}[/bold] …")
    rc = compose.up(cwd, build=build, pull=pull)
    if rc != 0:
        raise typer.Exit(rc)


def down(
    volumes: Annotated[
        bool, typer.Option("--volumes", help="Also remove persistent data volumes.")
    ] = False,
) -> None:
    """Stop all running services for the current project."""
    cwd = _project_dir()
    if volumes:
        confirmed = typer.confirm(
            "⚠️  This will delete all persistent volumes (data loss). Continue?",
            default=False,
        )
        if not confirmed:
            raise typer.Abort()
    console.print(f"[cyan]Stopping stack in[/cyan] [bold]{cwd}[/bold] …")
    rc = compose.down(cwd, volumes=volumes)
    if rc != 0:
        raise typer.Exit(rc)


def status() -> None:
    """Print a service status table."""
    cwd = _project_dir()
    services = compose.ps(cwd)

    if not services:
        console.print("[yellow]No services found. Is the stack running?[/yellow]")
        return

    table = Table(title=f"Stack status — {cwd.name}", show_lines=False)
    table.add_column("Service", style="bold")
    table.add_column("Status")
    table.add_column("Health")
    table.add_column("Ports")

    for svc in services:
        name = svc.get("Service") or svc.get("Name", "?")
        state = svc.get("State", "?")
        health = svc.get("Health", "")
        ports_raw = svc.get("Publishers") or []

        # Format ports from Publishers list
        ports: list[str] = []
        if isinstance(ports_raw, list):
            for p in ports_raw:
                pub = p.get("PublishedPort", 0)
                target = p.get("TargetPort", 0)
                proto = p.get("Protocol", "tcp")
                if pub:
                    ports.append(f"{pub}→{target}/{proto}")
        port_str = ", ".join(ports) if ports else ""

        state_fmt = (
            f"[green]{state}[/green]"
            if state == "running"
            else f"[red]{state}[/red]"
            if state == "exited"
            else state
        )
        health_fmt = (
            f"[green]{health}[/green]"
            if health == "healthy"
            else f"[yellow]{health}[/yellow]"
            if health in ("starting", "unhealthy")
            else health
        )

        table.add_row(name, state_fmt, health_fmt, port_str)

    console.print(table)


def logs(
    service: Annotated[Optional[str], typer.Argument(help="Service name to stream.")] = None,
    tail: Annotated[Optional[int], typer.Option("--tail", help="Lines from end of log.")] = 100,
    no_follow: Annotated[
        bool, typer.Option("--no-follow", help="Print once and exit.")
    ] = False,
) -> None:
    """Stream logs from services."""
    cwd = _project_dir()
    rc = compose.logs(cwd, service=service, tail=tail, follow=not no_follow)
    if rc != 0:
        raise typer.Exit(rc)
