"""p4n4 validate: validate project configuration."""

from __future__ import annotations

import typer
from p4n4_lib import manifest as mf
from p4n4_lib.validate import validate_project
from rich.console import Console

from p4n4.project import require_manifest

console = Console()


def cmd() -> None:
    """Validate the current project's configuration and manifest."""
    manifest_path = require_manifest()
    project_dir = manifest_path.parent
    console.print(f"Validating project at [bold]{project_dir}[/bold] …\n")

    try:
        data = mf.load(manifest_path)
    except Exception as exc:
        console.print(f"[red]✗[/red] .p4n4.json is not valid JSON: {exc}")
        raise typer.Exit(1) from exc

    passed, errors = validate_project(project_dir, data)

    for label in passed:
        console.print(f"[green]✓[/green] {label}")

    if errors:
        console.print()
        for err in errors:
            console.print(f"[red]✗[/red] {err}")
        console.print(f"\n[red]Validation failed[/red] - {len(errors)} issue(s) found.")
        raise typer.Exit(1)
    else:
        console.print("\n[green]All checks passed.[/green]")
