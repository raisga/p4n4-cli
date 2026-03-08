"""p4n4 validate — validate project configuration."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def cmd() -> None:
    """Validate the current project's configuration and manifest."""
    console.print("[yellow]p4n4 validate[/yellow] — not yet implemented")
    raise typer.Exit(1)
