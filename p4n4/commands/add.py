"""p4n4 add — add a layer or service to an existing project."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

console = Console()


def cmd(
    component: Annotated[str, typer.Argument(help="Layer or service to add (e.g. ai, edge).")],
) -> None:
    """Add a layer or service to the current project."""
    console.print(f"[yellow]p4n4 add[/yellow] — not yet implemented (component: {component})")
    raise typer.Exit(1)
