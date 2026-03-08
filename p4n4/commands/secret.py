"""p4n4 secret — secret generation and rotation."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def cmd() -> None:
    """Generate or rotate project secrets."""
    console.print("[yellow]p4n4 secret[/yellow] — not yet implemented")
    raise typer.Exit(1)
