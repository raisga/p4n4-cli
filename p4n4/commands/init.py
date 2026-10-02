"""p4n4 init: interactive project scaffold wizard."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import questionary
import typer
from p4n4_lib import layout, scaffold
from p4n4_lib import manifest as mf
from p4n4_lib import secrets as secretutil
from p4n4_lib.layers import LAYERS
from rich.console import Console
from rich.panel import Panel

console = Console()


def _ask(prompt: str, default: str) -> str:
    return questionary.text(prompt, default=default).ask() or default


def _ask_password(prompt: str, default: str) -> str:
    return questionary.password(prompt).ask() or default


def _parse_host_port(value: str) -> tuple[str, str]:
    """Split "host[:port]" into (host, port); the port is "" when absent."""
    host, sep, port = value.rpartition(":")
    if not sep:
        return value, ""
    if not host or not port.isdigit() or not 0 < int(port) < 65536:
        raise typer.BadParameter(f"expected HOST or HOST:PORT, got '{value}'")
    return host, port


def _mqtt_remote_values(
    host: str,
    port: str,
    user: str,
    password: str,
    topics: str,
    prefix: str,
    tls: bool,
    ca_file: str,
) -> dict[str, str]:
    """
    .env values for the IoT stack's bridge to an external MQTT broker
    (config/mosquitto/bridge.sh): topics are pulled in, never published back.
    """
    if any(" " in v for v in (host, user, prefix)):
        raise typer.BadParameter("broker host, username and prefix may not contain spaces")
    if password and not user:
        raise typer.BadParameter("an external broker password needs a username")
    return {
        "MQTT_REMOTE_HOST": host,
        "MQTT_REMOTE_PORT": port,
        "MQTT_REMOTE_USER": user,
        "MQTT_REMOTE_PASSWORD": password,
        "MQTT_REMOTE_TOPICS": topics,
        "MQTT_REMOTE_PREFIX": prefix,
        "MQTT_REMOTE_TLS": "true" if tls else "false",
        "MQTT_REMOTE_CA_FILE": ca_file,
    }


def _ask_mqtt_remote() -> tuple[dict[str, str], Path | None]:
    """Wizard step for the external broker bridge. Returns its .env values (empty
    when declined) and a CA certificate to copy into the project, if any."""
    if not questionary.confirm(
        "Pull topics from an external MQTT broker (like mosquitto_sub -h <host>)?",
        default=False,
    ).ask():
        return {}, None
    host, port = _parse_host_port(questionary.text("Broker host (HOST or HOST:PORT)").ask() or "")
    if not host:
        console.print("[yellow]No host given: skipping the external broker.[/yellow]")
        return {}, None
    user = _ask("Username (leave blank for none)", "")
    password = questionary.password("Password (leave blank for none)").ask() or ""
    topics = _ask("Topics to pull in (comma-separated)", "sensors/#")
    prefix = _ask("Local topic prefix, e.g. remote/ (leave blank for none)", "")
    tls = bool(questionary.confirm("Connect over TLS?", default=port == "8883").ask())
    ca_path = None
    if tls:
        ca = _ask("CA certificate file (leave blank for the system CAs)", "")
        if ca:
            ca_path = Path(ca).expanduser()
            if not ca_path.is_file():
                raise typer.BadParameter(f"CA certificate not found: {ca_path}")
    values = _mqtt_remote_values(
        host, port, user, password, topics, prefix, tls, ca_path.name if ca_path else ""
    )
    return values, ca_path


def _scaffold(
    project_dir: Path,
    layers: list[str],
    layer_name: str,
    env_values: dict[str, str],
    source: str | None,
) -> None:
    """Scaffold one layer into its layout directory (project root, or a
    per-layer subdirectory for multi-layer projects)."""
    layer = LAYERS[layer_name]
    dest = layout.layer_dir(project_dir, layers, layer_name)
    dest.mkdir(parents=True, exist_ok=True)
    if source is None:
        console.print(f"  Cloning [bold]{layer.repo_url}[/bold] …")
    scaffold.scaffold_layer(dest, layer, env_values, source=source)


def cmd(
    project_name: Annotated[str, typer.Argument(help="Name of the new project directory.")],
    layer: Annotated[
        str,
        typer.Option("--layer", help="Layer(s) to enable: iot, ai, edge, dashboard, all."),
    ] = "iot",
    no_interactive: Annotated[
        bool, typer.Option("--no-interactive", help="Skip wizard and use defaults.")
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source-iot",
            help="Local path to a p4n4-iot checkout (skips git clone; useful offline).",
        ),
    ] = None,
    ai_source: Annotated[
        str | None,
        typer.Option(
            "--source-ai",
            help="Local path to a p4n4-ai checkout (skips git clone; useful offline).",
        ),
    ] = None,
    edge_source: Annotated[
        str | None,
        typer.Option(
            "--source-edge",
            help="Local path to a p4n4-edge checkout (skips git clone; useful offline).",
        ),
    ] = None,
    dashboard_source: Annotated[
        str | None,
        typer.Option(
            "--source-dashboard",
            help="Local path to a p4n4-dashboard checkout (skips git clone; useful offline).",
        ),
    ] = None,
    mqtt_remote: Annotated[
        str | None,
        typer.Option(
            "--mqtt-remote",
            metavar="HOST[:PORT]",
            help="Bridge topics in from an external MQTT broker (IoT layer).",
            rich_help_panel="External MQTT broker",
        ),
    ] = None,
    mqtt_remote_user: Annotated[
        str,
        typer.Option(
            "--mqtt-remote-user",
            help="Username on the external broker.",
            rich_help_panel="External MQTT broker",
        ),
    ] = "",
    mqtt_remote_password: Annotated[
        str,
        typer.Option(
            "--mqtt-remote-password",
            envvar="P4N4_MQTT_REMOTE_PASSWORD",
            show_envvar=True,
            help="Password on the external broker (prefer the env var: keeps it out of "
            "shell history).",
            rich_help_panel="External MQTT broker",
        ),
    ] = "",
    mqtt_remote_topics: Annotated[
        str,
        typer.Option(
            "--mqtt-remote-topics",
            help="Comma-separated topic filters to pull in.",
            rich_help_panel="External MQTT broker",
        ),
    ] = "sensors/#",
    mqtt_remote_tls: Annotated[
        bool,
        typer.Option(
            "--mqtt-remote-tls",
            help="Connect to the external broker over TLS (port 8883 by default).",
            rich_help_panel="External MQTT broker",
        ),
    ] = False,
    mqtt_remote_ca: Annotated[
        Path | None,
        typer.Option(
            "--mqtt-remote-ca",
            exists=True,
            dir_okay=False,
            help="CA certificate for the external broker's TLS (default: system CAs).",
            rich_help_panel="External MQTT broker",
        ),
    ] = None,
) -> None:
    """Scaffold a new P4N4 project."""
    project_dir = Path.cwd() / project_name

    if project_dir.exists():
        console.print(f"[red]Error:[/red] Directory '[bold]{project_name}[/bold]' already exists.")
        raise typer.Exit(1)

    # "all" follows the registry, so new layers (the dashboard) are included
    layers = list(LAYERS) if layer == "all" else [lyr.strip() for lyr in layer.split(",")]
    unknown = [lyr for lyr in layers if lyr not in LAYERS]
    if unknown or not layers:
        console.print(
            f"[red]Error:[/red] Unknown layer(s): [bold]{', '.join(unknown) or layer}[/bold]. "
            f"Choose from {', '.join(LAYERS)} or all."
        )
        raise typer.Exit(1)

    if mqtt_remote and "iot" not in layers:
        console.print(
            "[red]Error:[/red] [bold]--mqtt-remote[/bold] bridges into the IoT layer's broker; "
            "add [bold]iot[/bold] to --layer."
        )
        raise typer.Exit(1)

    # Flags configure the bridge directly; otherwise the wizard offers it
    mqtt_remote_env: dict[str, str] = {}
    if mqtt_remote_ca and not (mqtt_remote and mqtt_remote_tls):
        console.print(
            "[red]Error:[/red] [bold]--mqtt-remote-ca[/bold] needs "
            "[bold]--mqtt-remote[/bold] and [bold]--mqtt-remote-tls[/bold]."
        )
        raise typer.Exit(1)
    if mqtt_remote:
        host, port = _parse_host_port(mqtt_remote)
        mqtt_remote_env = _mqtt_remote_values(
            host,
            port,
            mqtt_remote_user,
            mqtt_remote_password,
            mqtt_remote_topics,
            "",
            mqtt_remote_tls,
            mqtt_remote_ca.name if mqtt_remote_ca else "",
        )

    console.print(
        Panel(
            f"[bold cyan]p4n4 init[/bold cyan]: scaffolding [bold]{project_name}[/bold]",
            expand=False,
        )
    )

    # ── Collect configuration ─────────────────────────────────────────────────
    if no_interactive:
        org = "ming"
        tz = "UTC"
        influx_password = secretutil.token(12)
        influx_token = secretutil.token(32)
        grafana_password = secretutil.token(12)
        node_red_password = secretutil.token(12)
        letta_password = secretutil.token(12)
        n8n_password = secretutil.token(12)
        n8n_encryption_key = secretutil.token(16)
        n8n_host = "localhost"
    else:
        console.print("\n[dim]Press Enter to accept defaults.[/dim]\n")
        org = _ask("InfluxDB organisation", "ming")
        tz = _ask("Timezone (TZ database name)", "UTC")
        influx_password = _ask_password(
            "InfluxDB admin password (leave blank to auto-generate)",
            secretutil.token(12),
        )
        influx_token = _ask_password(
            "InfluxDB API token (leave blank to auto-generate)",
            secretutil.token(32),
        )
        grafana_password = _ask_password(
            "Grafana admin password (leave blank to auto-generate)",
            secretutil.token(12),
        )
        node_red_password = _ask_password(
            "Node-RED editor password (leave blank to auto-generate)",
            secretutil.token(12),
        )
        if "iot" in layers and not mqtt_remote:
            console.print("\n[dim]External MQTT broker (optional):[/dim]\n")
            mqtt_remote_env, mqtt_remote_ca = _ask_mqtt_remote()
        if "ai" in layers:
            console.print("\n[dim]GenAI stack configuration:[/dim]\n")
            letta_password = _ask_password(
                "Letta server password (leave blank to auto-generate)",
                secretutil.token(12),
            )
            n8n_password = _ask_password(
                "n8n admin password (leave blank to auto-generate)",
                secretutil.token(12),
            )
            n8n_encryption_key = _ask_password(
                "n8n encryption key (leave blank to auto-generate, must be 32+ chars)",
                secretutil.token(16),
            )
            n8n_host = _ask("n8n hostname (for webhooks)", "localhost")
        else:
            letta_password = secretutil.token(12)
            n8n_password = secretutil.token(12)
            n8n_encryption_key = secretutil.token(16)
            n8n_host = "localhost"

    iot_env_values: dict[str, str] = {
        "TZ": tz,
        "INFLUXDB_USERNAME": "admin",
        "INFLUXDB_PASSWORD": influx_password,
        "INFLUXDB_ORG": org,
        "INFLUXDB_TOKEN": influx_token,
        "INFLUXDB_BUCKET": "raw_telemetry",
        "INFLUXDB_BUCKET_PROCESSED": "processed_metrics",
        "INFLUXDB_BUCKET_AI_EVENTS": "ai_events",
        "INFLUXDB_BUCKET_HEALTH": "system_health",
        "INFLUXDB_SANDBOX_BUCKET": "sandbox",
        "INFLUXDB_SANDBOX_RETENTION": "30d",
        "GRAFANA_USER": "admin",
        "GRAFANA_PASSWORD": grafana_password,
        "NODE_RED_USER": "admin",
        "NODE_RED_PASSWORD": node_red_password,
        # The dashboard's web UI frames Grafana in its Grafana tab
        "GRAFANA_ALLOW_EMBEDDING": "true" if "dashboard" in layers else "false",
        **mqtt_remote_env,
    }

    ai_env_values: dict[str, str] = {
        "LETTA_SERVER_PASSWORD": letta_password,
        "N8N_BASIC_AUTH_USER": "admin",
        "N8N_BASIC_AUTH_PASSWORD": n8n_password,
        "N8N_ENCRYPTION_KEY": n8n_encryption_key,
        "N8N_HOST": n8n_host,
        # Shared InfluxDB values (must match p4n4-iot when used alongside it)
        "INFLUXDB_TOKEN": influx_token,
        "INFLUXDB_ORG": org,
        "INFLUXDB_BUCKET": "raw_telemetry",
    }

    edge_env_values: dict[str, str] = {
        "TZ": tz,
        # Shared InfluxDB values (must match p4n4-iot when used alongside it)
        "INFLUXDB_TOKEN": influx_token,
        "INFLUXDB_ORG": org,
        "INFLUXDB_BUCKET_AI_EVENTS": "ai_events",
    }

    # ── Create project directory and scaffold ─────────────────────────────────
    project_dir.mkdir(parents=True)

    try:
        if "iot" in layers:
            _scaffold(project_dir, layers, "iot", iot_env_values, source)
            if mqtt_remote_ca:
                certs = layout.layer_dir(project_dir, layers, "iot") / "config/mosquitto/certs"
                certs.mkdir(parents=True, exist_ok=True)
                shutil.copy2(mqtt_remote_ca, certs / mqtt_remote_ca.name)

        if "ai" in layers:
            _scaffold(project_dir, layers, "ai", ai_env_values, ai_source)

        if "edge" in layers:
            _scaffold(project_dir, layers, "edge", edge_env_values, edge_source)

        # The dashboard has no secrets yet: its .env is the repo's .env.example
        if "dashboard" in layers:
            _scaffold(project_dir, layers, "dashboard", {}, dashboard_source)

        mf.save(project_dir / mf.MANIFEST_FILE, mf.create(project_name, layers))

    except Exception as exc:
        shutil.rmtree(project_dir, ignore_errors=True)
        console.print(f"[red]Scaffold failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(f"\n[green]✓[/green] Project created at [bold]{project_dir}[/bold]\n")
    console.print("  [dim]Files generated:[/dim]")
    for f in sorted(project_dir.rglob("*")):
        if f.is_file():
            console.print(f"    {f.relative_to(project_dir)}")

    if mqtt_remote_env:
        console.print(
            f"\n  [dim]Bridging[/dim] {mqtt_remote_env['MQTT_REMOTE_TOPICS']} "
            f"[dim]from[/dim] {mqtt_remote_env['MQTT_REMOTE_HOST']} "
            "[dim](MQTT_REMOTE_* in the IoT .env)[/dim]"
        )

    console.print(f"\n[bold]Next steps:[/bold]\n  cd {project_name}\n  p4n4 up\n")
