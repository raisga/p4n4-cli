"""p4n4 up / down / status / logs: stack lifecycle commands."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from p4n4_lib import compose, layout
from p4n4_lib import env as envutil
from p4n4_lib import manifest as mf
from rich.console import Console
from rich.table import Table

from p4n4.project import require_compose_dirs

console = Console()

EMU = "p4n4-emu"
EMU_INSTALL = "uv tool install git+https://github.com/raisga/p4n4-emu"
# Compose records the files a container was created from in this label; p4n4-emu's
# resource-limit overlays are named <stack>.emu.yml
_CONFIG_FILES_LABEL = "com.docker.compose.project.config_files="
_EMU_OVERLAY_SUFFIX = ".emu.yml"


@contextmanager
def _compose_errors() -> Iterator[None]:
    try:
        yield
    except (compose.ComposeNotFoundError, compose.DockerError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


def dashboard_url(cwd: Path) -> str:
    """Where the dashboard layer in `cwd` listens, from its .env (DASHBOARD_PORT, _BIND)."""
    env_path = cwd / envutil.ENV_FILE
    env = envutil.load(env_path) if env_path.exists() else {}
    bind = env.get("DASHBOARD_BIND") or "0.0.0.0"
    host = "localhost" if bind in ("0.0.0.0", "::") else bind
    return f"http://{host}:{env.get('DASHBOARD_PORT') or '8088'}"


def _stop_hint(conflict: compose.NameConflict) -> str:
    """The command that frees the container name `conflict` holds."""
    wd = conflict.working_dir
    if conflict.project is None:
        return f"docker rm -f {conflict.name}"
    if wd is None or not wd.is_dir():
        return f"docker compose -p {conflict.project} down"
    manifest_path = mf.find(wd)
    if manifest_path is not None:
        return f"cd {manifest_path.parent} && p4n4 down"
    return f"cd {wd} && docker compose down"


def _check_name_conflicts(dirs: list[tuple[str, Path]]) -> None:
    """Exit before starting anything if another project holds this one's container names."""
    with _compose_errors():
        conflicts = compose.name_conflicts(*(cwd for _, cwd in dirs))
    if not conflicts:
        return

    console.print("[red]Error:[/red] Container names this project uses are already taken:")
    for c in conflicts:
        owner = f"project [bold]{c.project}[/bold]" if c.project else "a container outside Compose"
        where = f" in {c.working_dir}" if c.working_dir else ""
        console.print(f"  [bold]{c.name}[/bold] ({c.state}) — {owner}{where}")
    console.print(
        "\np4n4 stacks use fixed container names and host ports, so only one project "
        "can run on a host at a time. Stop the other one first:"
    )
    for hint in dict.fromkeys(_stop_hint(c) for c in conflicts):
        console.print(f"  [bold]{hint}[/bold]", soft_wrap=True)
    console.print("Or stop every p4n4 project at once: [bold]p4n4 down --all[/bold]")
    raise typer.Exit(1)


def _emu_up(
    dirs: list[tuple[str, Path]], profile: str, build: bool, pull: bool
) -> int:
    """Start the stacks under p4n4-emu's hardware profile `profile`."""
    emu = shutil.which(EMU)
    if emu is None:
        console.print(
            f"[red]Error:[/red] --emu needs {EMU}, which isn't installed. "
            f"Install it with: [bold]{EMU_INSTALL}[/bold]"
        )
        raise typer.Exit(1)
    names = ",".join(name for name, _ in dirs)
    cmd = [emu, "up", "--profile", profile, "--stack", names]
    if build:
        cmd.append("--build")
    if pull:
        cmd.append("--pull")
    console.print(f"[cyan]Starting [bold]{names}[/bold] under p4n4-emu ({profile}) ...[/cyan]")
    # p4n4-emu resolves the stacks from the project's .p4n4.json, as p4n4 does
    return subprocess.run(cmd, cwd=dirs[0][1], check=False).returncode


def up(
    stack: Annotated[
        str | None, typer.Argument(help="Stack to start: iot, ai, edge, dashboard.")
    ] = None,
    build: Annotated[bool, typer.Option("--build", help="Rebuild images before starting.")] = False,
    pull: Annotated[
        bool, typer.Option("--pull", help="Pull latest images before starting.")
    ] = False,
    no_detach: Annotated[
        bool, typer.Option("--no-detach", help="Run in foreground (do not detach).")
    ] = False,
    emu: Annotated[
        str | None,
        typer.Option(
            "--emu",
            metavar="PROFILE",
            help="Run under p4n4-emu with a hardware profile (rpi4, rpi5, nuc, ...): "
            "the device's CPU, memory and disk limits, and its architecture.",
        ),
    ] = None,
) -> None:
    """Start one or all enabled stacks in dependency order."""
    if emu and no_detach:
        console.print("[red]Error:[/red] --emu starts the stacks detached; drop --no-detach.")
        raise typer.Exit(1)
    dirs = require_compose_dirs(stack)
    _check_name_conflicts(dirs)
    if emu:
        rc = _emu_up(dirs, emu, build, pull)
        if rc != 0:
            raise typer.Exit(rc)
    else:
        for name, cwd in dirs:
            console.print(
                f"[cyan]Starting [bold]{name}[/bold] stack in[/cyan] [bold]{cwd}[/bold] ..."
            )
            with _compose_errors():
                # Stacks that declare p4n4-net external need it to exist (an AI-only
                # project, or `p4n4 up ai` while iot is down). iot declares it itself, but
                # a p4n4-net made by `docker network create` lacks Compose's label and
                # stops iot with "incorrect label"; ensure_network recreates it with the
                # label while no container uses it.
                if compose.ensure_network(layout.NETWORK, layout.NETWORK_SUBNET):
                    console.print(f"[dim]Created the {layout.NETWORK} network.[/dim]")
                rc = compose.up(cwd, build=build, pull=pull, detach=not no_detach)
            if rc != 0:
                raise typer.Exit(rc)
    for name, cwd in dirs:
        if name == "dashboard":
            console.print(f"[green]Dashboard:[/green] {dashboard_url(cwd)}")


def _down_all(volumes: bool) -> None:
    """Stop every p4n4 project on this host, whichever directory it lives in."""
    with _compose_errors():
        projects = compose.host_projects()
    if not projects:
        console.print("[green]No p4n4 containers on this host.[/green]")
        return

    console.print("This stops every p4n4 project on this host:")
    for project in projects:
        if project.name is None:
            console.print("  [bold]Containers outside Compose[/bold]")
        else:
            where = f" in {project.working_dir}" if project.working_dir else ""
            console.print(f"  [bold]{project.name}[/bold]{where}")
        names = ", ".join(f"{name} ({state})" for name, state in project.containers)
        console.print(f"    {names}", soft_wrap=True)
    prompt = (
        "This also deletes their persistent volumes (data loss). Continue?"
        if volumes
        else "Stop them all?"
    )
    if not typer.confirm(prompt, default=False):
        raise typer.Abort()

    failed = []
    for project in projects:
        label = project.name or "containers outside Compose"
        console.print(f"[cyan]Stopping [bold]{label}[/bold] ...[/cyan]")
        with _compose_errors():
            if compose.down_project(project, volumes=volumes) != 0:
                failed.append(label)
    if failed:
        console.print(f"[red]Error:[/red] Could not stop: {', '.join(failed)}")
        raise typer.Exit(1)


def down(
    stack: Annotated[
        str | None, typer.Argument(help="Stack to stop: iot, ai, edge, dashboard.")
    ] = None,
    volumes: Annotated[
        bool, typer.Option("--volumes", help="Also remove persistent data volumes.")
    ] = False,
    all_projects: Annotated[
        bool,
        typer.Option("--all", help="Stop every p4n4 project on this host, run from any directory."),
    ] = False,
) -> None:
    """Stop one or all running stacks."""
    if all_projects:
        if stack:
            console.print("[red]Error:[/red] --all stops every project; drop the stack name.")
            raise typer.Exit(1)
        _down_all(volumes)
        return
    dirs = require_compose_dirs(stack)
    if volumes:
        confirmed = typer.confirm(
            "This will delete all persistent volumes (data loss). Continue?",
            default=False,
        )
        if not confirmed:
            raise typer.Abort()
    # Reverse dependency order: dependents stop before the stacks they rely on
    emu = shutil.which(EMU)
    for name, cwd in reversed(dirs):
        console.print(f"[cyan]Stopping [bold]{name}[/bold] stack in[/cyan] [bold]{cwd}[/bold] ...")
        if emu and _runs_under_emu(cwd):
            # p4n4-emu also removes its overlay, and the simulator with iot
            cmd = [emu, "down", "--stack", name] + (["--volumes", "--yes"] if volumes else [])
            rc = subprocess.run(cmd, cwd=cwd, check=False).returncode
        else:
            with _compose_errors():
                rc = compose.down(cwd, volumes=volumes)
        if rc != 0:
            raise typer.Exit(rc)


def _runs_under_emu(cwd: Path) -> bool:
    """Whether the stack's containers were created with a p4n4-emu overlay."""
    try:
        services = compose.ps(cwd)
    except (compose.ComposeNotFoundError, compose.DockerError):
        return False
    for svc in services:
        labels = svc.get("Labels") or ""
        files = labels.partition(_CONFIG_FILES_LABEL)[2]
        # The label's value is comma-separated too, so look up to the next label
        files = files.split(",com.docker.", 1)[0]
        if any(f.endswith(_EMU_OVERLAY_SUFFIX) for f in files.split(",")):
            return True
    return False


def status() -> None:
    """Print a service status table."""
    for name, cwd in require_compose_dirs():
        with _compose_errors():
            services = compose.ps(cwd)

        if not services:
            console.print(
                f"[yellow]No services found for stack '{name}'. Is the stack running?[/yellow]"
            )
            continue

        table = Table(title=f"Stack status: {name}", show_lines=False)
        table.add_column("Service", style="bold")
        table.add_column("Status")
        table.add_column("Health")
        table.add_column("Ports")

        for svc in services:
            svc_name = svc.get("Service") or svc.get("Name", "?")
            state = svc.get("State", "?")
            health = svc.get("Health", "")
            ports_raw = svc.get("Publishers") or []

            # Format ports from Publishers list
            ports: list[str] = []
            if isinstance(ports_raw, list):
                for p in ports_raw:
                    pub = p.get("PublishedPort", 0)
                    target = p.get("TargetPort", 0)
                    proto = p.get("Protocol", "tcp")
                    if pub:
                        ports.append(f"{pub}→{target}/{proto}")
            port_str = ", ".join(ports) if ports else ""

            state_fmt = (
                f"[green]{state}[/green]"
                if state == "running"
                else f"[red]{state}[/red]"
                if state == "exited"
                else state
            )
            health_fmt = (
                f"[green]{health}[/green]"
                if health == "healthy"
                else f"[yellow]{health}[/yellow]"
                if health in ("starting", "unhealthy")
                else health
            )

            table.add_row(svc_name, state_fmt, health_fmt, port_str)

        console.print(table)


def logs(
    service: Annotated[str | None, typer.Argument(help="Service name to stream.")] = None,
    stack: Annotated[
        str | None, typer.Option("--stack", help="Stack to read logs from: iot, ai, edge.")
    ] = None,
    tail: Annotated[int | None, typer.Option("--tail", help="Lines from end of log.")] = 100,
    no_follow: Annotated[bool, typer.Option("--no-follow", help="Print once and exit.")] = False,
) -> None:
    """Stream logs from services."""
    dirs = require_compose_dirs(stack)
    if len(dirs) > 1 and not no_follow:
        console.print(
            "[red]Error:[/red] This project has multiple stacks. "
            "Pass [bold]--stack <name>[/bold] to follow one stack's logs, "
            "or [bold]--no-follow[/bold] to print logs from all stacks."
        )
        raise typer.Exit(1)
    for _name, cwd in dirs:
        with _compose_errors():
            rc = compose.logs(cwd, service=service, tail=tail, follow=not no_follow)
        if rc != 0:
            raise typer.Exit(rc)
