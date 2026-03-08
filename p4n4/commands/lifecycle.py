"""p4n4 up / down / status / logs — stack lifecycle commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.console import Console

console = Console()


def up(
    edge: Annotated[bool, typer.Option("--edge", help="Start Edge AI services only.")] = False,
    ai: Annotated[bool, typer.Option("--ai", help="Start Gen AI services only.")] = False,
    build: Annotated[bool, typer.Option("--build", help="Rebuild images before starting.")] = False,
    pull: Annotated[bool, typer.Option("--pull", help="Pull latest images before starting.")] = False,
) -> None:
    """Start the project stack."""
    console.print("[yellow]p4n4 up[/yellow] — not yet implemented")
    raise typer.Exit(1)


def down(
    volumes: Annotated[
        bool, typer.Option("--volumes", help="Also remove persistent data volumes.")
    ] = False,
) -> None:
    """Stop all running services for the current project."""
    console.print("[yellow]p4n4 down[/yellow] — not yet implemented")
    raise typer.Exit(1)


def status() -> None:
    """Print a service status table."""
    console.print("[yellow]p4n4 status[/yellow] — not yet implemented")
    raise typer.Exit(1)


def logs(
    service: Annotated[Optional[str], typer.Argument(help="Service name to stream.")] = None,
    tail: Annotated[Optional[int], typer.Option("--tail", help="Lines from end of log.")] = None,
    no_follow: Annotated[
        bool, typer.Option("--no-follow", help="Print once and exit.")
    ] = False,
) -> None:
    """Stream logs from services."""
    console.print("[yellow]p4n4 logs[/yellow] — not yet implemented")
    raise typer.Exit(1)
