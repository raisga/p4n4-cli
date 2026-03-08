"""p4n4 upgrade — upgrade stack images or CLI templates."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def cmd() -> None:
    """Upgrade stack images or bundled CLI templates."""
    console.print("[yellow]p4n4 upgrade[/yellow] — not yet implemented")
    raise typer.Exit(1)
