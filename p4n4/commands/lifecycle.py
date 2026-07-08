"""p4n4 up / down / status / logs: stack lifecycle commands."""

from __future__ import annotations

from typing import Annotated

import typer
from p4n4_lib import compose
from rich.console import Console
from rich.table import Table

from p4n4.project import require_compose_dirs

console = Console()


def up(
    stack: Annotated[str | None, typer.Argument(help="Stack to start: iot, ai, edge.")] = None,
    build: Annotated[bool, typer.Option("--build", help="Rebuild images before starting.")] = False,
    pull: Annotated[
        bool, typer.Option("--pull", help="Pull latest images before starting.")
    ] = False,
    no_detach: Annotated[
        bool, typer.Option("--no-detach", help="Run in foreground (do not detach).")
    ] = False,
) -> None:
    """Start one or all enabled stacks in dependency order."""
    for name, cwd in require_compose_dirs(stack):
        console.print(f"[cyan]Starting [bold]{name}[/bold] stack in[/cyan] [bold]{cwd}[/bold] ...")
        rc = compose.up(cwd, build=build, pull=pull, detach=not no_detach)
        if rc != 0:
            raise typer.Exit(rc)


def down(
    stack: Annotated[str | None, typer.Argument(help="Stack to stop: iot, ai, edge.")] = None,
    volumes: Annotated[
        bool, typer.Option("--volumes", help="Also remove persistent data volumes.")
    ] = False,
) -> None:
    """Stop one or all running stacks."""
    dirs = require_compose_dirs(stack)
    if volumes:
        confirmed = typer.confirm(
            "This will delete all persistent volumes (data loss). Continue?",
            default=False,
        )
        if not confirmed:
            raise typer.Abort()
    # Reverse dependency order: dependents stop before the stacks they rely on
    for name, cwd in reversed(dirs):
        console.print(f"[cyan]Stopping [bold]{name}[/bold] stack in[/cyan] [bold]{cwd}[/bold] ...")
        rc = compose.down(cwd, volumes=volumes)
        if rc != 0:
            raise typer.Exit(rc)


def status() -> None:
    """Print a service status table."""
    for name, cwd in require_compose_dirs():
        services = compose.ps(cwd)

        if not services:
            console.print(
                f"[yellow]No services found for stack '{name}'. Is the stack running?[/yellow]"
            )
            continue

        table = Table(title=f"Stack status: {name}", show_lines=False)
        table.add_column("Service", style="bold")
        table.add_column("Status")
        table.add_column("Health")
        table.add_column("Ports")

        for svc in services:
            svc_name = svc.get("Service") or svc.get("Name", "?")
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

            table.add_row(svc_name, state_fmt, health_fmt, port_str)

        console.print(table)


def logs(
    service: Annotated[str | None, typer.Argument(help="Service name to stream.")] = None,
    stack: Annotated[
        str | None, typer.Option("--stack", help="Stack to read logs from: iot, ai, edge.")
    ] = None,
    tail: Annotated[int | None, typer.Option("--tail", help="Lines from end of log.")] = 100,
    no_follow: Annotated[bool, typer.Option("--no-follow", help="Print once and exit.")] = False,
) -> None:
    """Stream logs from services."""
    dirs = require_compose_dirs(stack)
    if len(dirs) > 1 and not no_follow:
        console.print(
            "[red]Error:[/red] This project has multiple stacks. "
            "Pass [bold]--stack <name>[/bold] to follow one stack's logs, "
            "or [bold]--no-follow[/bold] to print logs from all stacks."
        )
        raise typer.Exit(1)
    for _name, cwd in dirs:
        rc = compose.logs(cwd, service=service, tail=tail, follow=not no_follow)
        if rc != 0:
            raise typer.Exit(rc)
