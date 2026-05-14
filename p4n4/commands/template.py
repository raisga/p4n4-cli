"""p4n4 template -- community template registry commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Community template registry commands.")
console = Console()


@app.command("search")
def search(
    query: Annotated[str | None, typer.Argument(help="Search term.")] = None,
) -> None:
    """Search the community template registry."""
    console.print("[yellow]p4n4 template search[/yellow]: not yet implemented")
    raise typer.Exit(1)


@app.command("install")
def install(
    name: Annotated[str, typer.Argument(help="Template name or short-name.")],
) -> None:
    """Install a template into the current project."""
    console.print(f"[yellow]p4n4 template install[/yellow]: not yet implemented (template: {name})")
    raise typer.Exit(1)


@app.command("list")
def list_cmd() -> None:
    """Show installed templates."""
    console.print("[yellow]p4n4 template list[/yellow]: not yet implemented")
    raise typer.Exit(1)
