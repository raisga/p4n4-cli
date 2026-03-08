"""p4n4 ei — Edge Impulse subcommands."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(help="Edge Impulse management commands.")
console = Console()


@app.command("deploy")
def deploy() -> None:
    """Deploy an Edge Impulse model to the edge device."""
    console.print("[yellow]p4n4 ei deploy[/yellow] — not yet implemented")
    raise typer.Exit(1)


@app.command("run")
def run() -> None:
    """Run inference using a deployed Edge Impulse model."""
    console.print("[yellow]p4n4 ei run[/yellow] — not yet implemented")
    raise typer.Exit(1)
