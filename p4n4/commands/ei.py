"""p4n4 ei -- Edge Impulse subcommands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Edge Impulse management commands.")
console = Console()


@app.command("deploy")
def deploy(
    model_file: Annotated[str, typer.Argument(help="Path to .eim model file.")],
) -> None:
    """Copy a .eim model and restart the runner."""
    console.print(f"[yellow]p4n4 ei deploy[/yellow]: not yet implemented (model: {model_file})")
    raise typer.Exit(1)


@app.command("run")
def run() -> None:
    """Start the Edge Impulse runner."""
    console.print("[yellow]p4n4 ei run[/yellow]: not yet implemented")
    raise typer.Exit(1)


@app.command("status")
def status() -> None:
    """Show runner container status."""
    console.print("[yellow]p4n4 ei status[/yellow]: not yet implemented")
    raise typer.Exit(1)
