"""p4n4 remove — remove a layer or service from an existing project."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

console = Console()


def cmd(
    component: Annotated[str, typer.Argument(help="Layer or service to remove.")],
) -> None:
    """Remove a layer or service from the current project."""
    console.print(f"[yellow]p4n4 remove[/yellow] — not yet implemented (component: {component})")
    raise typer.Exit(1)
