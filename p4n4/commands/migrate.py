"""p4n4 migrate: move a legacy layer into the layer that replaced it."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from p4n4_lib import compose, layout
from p4n4_lib import manifest as mf
from p4n4_lib import migrate as mig
from p4n4_lib import secrets as secretutil
from p4n4_lib.layers import LEGACY_LAYERS, RUNNER_SERVICE
from rich.console import Console
from rich.table import Table

from p4n4.project import require_manifest

console = Console()


def _running(edge_dir: Path) -> list[str] | None:
    """The edge layer's running services; None when Docker can't be asked."""
    try:
        services = compose.ps(edge_dir)
    except (compose.ComposeNotFoundError, compose.DockerError):
        return None
    return [s.get("Service") or s.get("Name", "?") for s in services if s.get("State") == "running"]


def _new_ai_env() -> dict[str, str]:
    """Secrets for an ai layer the migration scaffolds, as `p4n4 init` generates them.
    The System 1 keys stay empty: `p4n4 ai system1 enable` generates them."""
    return {
        "LETTA_SERVER_PASSWORD": secretutil.token(12),
        "N8N_BASIC_AUTH_USER": "admin",
        "N8N_BASIC_AUTH_PASSWORD": secretutil.token(12),
        "N8N_ENCRYPTION_KEY": secretutil.token(16),
        "N8N_HOST": "localhost",
    }


def cmd(
    layer: Annotated[str, typer.Argument(help="Legacy layer to migrate: edge.")],
    source_ai: Annotated[
        str | None,
        typer.Option(
            "--source-ai",
            help="Local path to a p4n4-ai checkout, for a project without an ai layer "
            "(skips git clone; useful offline).",
        ),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Don't ask for confirmation.")] = False,
) -> None:
    """Move a legacy layer into the layer that replaced it (edge → ai or extras)."""
    if layer not in LEGACY_LAYERS:
        console.print(
            f"[red]Error:[/red] '[bold]{layer}[/bold]' is not a legacy layer. "
            f"Migratable: {', '.join(LEGACY_LAYERS)}."
        )
        raise typer.Exit(1)

    manifest_path = require_manifest()
    project_dir = manifest_path.parent
    layers: list[str] = mf.load(manifest_path).get("layers", [])
    if layer not in layers:
        console.print(f"[green]Nothing to migrate:[/green] this project has no {layer} layer.")
        return

    edge_dir = layout.layer_dir(project_dir, layers, layer)
    edge_compose = edge_dir / layout.COMPOSE_FILE
    if not edge_compose.exists():
        console.print(f"[red]Error:[/red] {edge_compose} not found.")
        raise typer.Exit(1)

    running = _running(edge_dir)
    if running:
        console.print(
            f"[red]Error:[/red] The {layer} layer is running ({', '.join(running)}). "
            f"Stop it first: [bold]p4n4 down {layer}[/bold]"
        )
        raise typer.Exit(1)
    if running is None:
        console.print(
            f"[yellow]Could not ask Docker whether the {layer} layer runs.[/yellow] "
            f"Make sure it's stopped ([bold]p4n4 down {layer}[/bold]) before going on."
        )

    try:
        target = mig.target_of(mig.load_compose(edge_compose))
    except mig.MigrateError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    scaffold_ai = target == "ai" and "ai" not in layers

    if target == "ai":
        console.print(
            f"The [bold]{layer}[/bold] layer runs the inference runner, which is now the ai "
            f"layer's [bold]{RUNNER_SERVICE}[/bold] profile. This moves its service, "
            "runner/, models and .env values into the ai layer"
            + (", scaffolded from p4n4-ai with only the runner enabled" if scaffold_ai else "")
            + f". The {layer} layer is kept in [bold]{mig.BACKUP_DIR}/[/bold]."
        )
    else:
        console.print(
            f"The [bold]{layer}[/bold] layer runs other services than the inference runner: "
            "it becomes the [bold]extras[/bold] layer (optional services), with the same "
            "containers and volumes."
        )
    if not yes and not typer.confirm("Migrate?", default=True):
        raise typer.Abort()

    if scaffold_ai and source_ai is None:
        console.print("  Cloning [bold]p4n4-ai[/bold] …")
    try:
        result = mig.migrate_edge(
            project_dir, source_ai=source_ai, new_env=_new_ai_env() if scaffold_ai else None
        )
    except mig.MigrateError as exc:
        console.print(f"[red]Migration failed, nothing changed:[/red] {exc}")
        raise typer.Exit(1) from exc

    where = result.target_dir.relative_to(project_dir).as_posix()
    where = "the project root" if where == "." else f"{where}/"
    console.print(f"\n[green]✓[/green] {layer} → [bold]{result.target}[/bold] ({where})")
    if result.scaffolded:
        console.print(
            f"[green]✓[/green] {result.target} layer scaffolded from p4n4-{result.target}"
        )
    if result.services_added:
        console.print(f"[green]✓[/green] Services: {', '.join(result.services_added)}")
    if result.files_copied:
        console.print(f"[green]✓[/green] Copied: {', '.join(result.files_copied)}")
    if result.env_added:
        console.print(f"[green]✓[/green] .env keys added: {', '.join(result.env_added)}")
    if result.profile_added:
        console.print(f"[green]✓[/green] {RUNNER_SERVICE} added to COMPOSE_PROFILES")
    if result.compose_project_name:
        console.print(
            f"[green]✓[/green] Compose project name kept: {result.compose_project_name} "
            "(same volumes)"
        )
    console.print(f"[green]✓[/green] .p4n4.json layers: {', '.join(result.layers)}")

    if result.env_conflicts:
        table = Table(title="Set differently in both .env files: the kept value is used")
        table.add_column("Key", style="bold")
        table.add_column(f"{result.target} (kept)")
        table.add_column(f"{layer} (not used)")
        for key, (kept, dropped) in result.env_conflicts.items():
            masked = key in secretutil.SECRET_KEYS or "PASSWORD" in key or "TOKEN" in key
            table.add_row(key, "****" if masked else kept, "****" if masked else dropped)
        console.print(table)

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  p4n4 validate")
    console.print(f"  p4n4 up {result.target}")
    if result.backup is not None:
        console.print(
            f"  [dim]Once it works, delete[/dim] {mig.BACKUP_DIR}/ [dim](the old {layer} "
            "layer). The old runner volume (*-edge_ei-runner-data) held nothing: remove it "
            "with docker volume rm.[/dim]"
        )
