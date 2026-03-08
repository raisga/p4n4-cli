"""p4n4 init — interactive project scaffold wizard."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

console = Console()


def cmd(
    project_name: Annotated[str, typer.Argument(help="Name of the new project directory.")],
    layer: Annotated[
        str,
        typer.Option("--layer", help="Layer(s) to enable: iot, ai, edge, all."),
    ] = "all",
    no_interactive: Annotated[
        bool, typer.Option("--no-interactive", help="Skip wizard and use defaults.")
    ] = False,
) -> None:
    """Scaffold a new P4N4 project."""
    console.print(
        f"[yellow]p4n4 init[/yellow] — not yet implemented\n"
        f"  project : [bold]{project_name}[/bold]\n"
        f"  layer   : {layer}\n"
        f"  interactive: {not no_interactive}"
    )
    raise typer.Exit(1)
