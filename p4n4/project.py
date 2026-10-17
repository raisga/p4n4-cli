"""Helpers for locating the current p4n4 project."""

from __future__ import annotations

from pathlib import Path

import typer
from p4n4_lib import layout
from p4n4_lib import manifest as mf
from p4n4_lib.layers import LEGACY_LAYERS, RUNNER_SERVICE
from rich.console import Console

console = Console()


def warn_legacy_layers(layers: list[str]) -> None:
    """Point a project still running a legacy layer at `p4n4 migrate`."""
    for name in layout.legacy(layers):
        console.print(
            f"[yellow]Warning:[/yellow] the [bold]{name}[/bold] layer merged into "
            f"[bold]{LEGACY_LAYERS[name]}[/bold] (its {RUNNER_SERVICE} profile). It keeps "
            f"working for now; move it with [bold]p4n4 migrate {name}[/bold].",
            soft_wrap=True,
        )


def require_manifest() -> Path:
    """Return the path to the nearest .p4n4.json, or exit with an error."""
    manifest_path = mf.find()
    if manifest_path is None:
        console.print(
            "[red]Error:[/red] No [bold].p4n4.json[/bold] found. "
            "Run [bold]p4n4 init <name>[/bold] first, or cd into a project directory."
        )
        raise typer.Exit(1)
    return manifest_path


def network_subnet(start: Path | None = None) -> str:
    """The subnet p4n4-net is created with: P4N4_SUBNET of the project holding `start`
    (default cwd), else the default."""
    manifest_path = mf.find(start)
    if manifest_path is None:
        return layout.NETWORK_SUBNET
    return layout.network_subnet(manifest_path.parent, mf.load(manifest_path).get("layers", []))


def require_compose_dirs(stack: str | None = None) -> list[tuple[str, Path]]:
    """
    Return (layer, directory) pairs holding this project's compose files, in
    dependency order — optionally filtered to a single stack. Exits with an
    error when nothing matches.
    """
    manifest_path = require_manifest()
    data = mf.load(manifest_path)
    warn_legacy_layers(data.get("layers", []))
    dirs = layout.compose_dirs(manifest_path.parent, data.get("layers", []))

    if stack:
        dirs = [(name, path) for name, path in dirs if name == stack]
        if not dirs:
            console.print(
                f"[red]Error:[/red] Stack '[bold]{stack}[/bold]' not found in this project."
            )
            raise typer.Exit(1)
    elif not dirs:
        console.print("[red]Error:[/red] No stack files found in this project.")
        raise typer.Exit(1)

    return dirs
