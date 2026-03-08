"""p4n4 CLI — entrypoint and command registration."""

from __future__ import annotations

import typer
from rich.console import Console

from p4n4 import __version__
from p4n4.commands import add, ei, init, lifecycle, remove, secret, template, upgrade, validate

app = typer.Typer(
    name="p4n4",
    help="Scaffold and manage P4N4 IoT / Edge AI projects.",
    add_completion=True,
    no_args_is_help=True,
)
console = Console()

# ── sub-apps ──────────────────────────────────────────────────────────────────
app.add_typer(ei.app, name="ei")
app.add_typer(template.app, name="template")

# ── top-level commands ────────────────────────────────────────────────────────
app.command("init")(init.cmd)
app.command("add")(add.cmd)
app.command("remove")(remove.cmd)
app.command("up")(lifecycle.up)
app.command("down")(lifecycle.down)
app.command("status")(lifecycle.status)
app.command("logs")(lifecycle.logs)
app.command("secret")(secret.cmd)
app.command("validate")(validate.cmd)
app.command("upgrade")(upgrade.cmd)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"p4n4 version [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: FBT001
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """p4n4 — Platform for Nexus Neural Network Nodes."""
