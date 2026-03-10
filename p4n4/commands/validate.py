"""p4n4 validate — validate project configuration."""

from __future__ import annotations

import typer
from rich.console import Console

from p4n4.utils import env as envutil
from p4n4.utils import manifest as mf

console = Console()

_REQUIRED_ENV_KEYS = {
    "iot": [
        "TZ",
        "INFLUXDB_USERNAME",
        "INFLUXDB_PASSWORD",
        "INFLUXDB_ORG",
        "INFLUXDB_TOKEN",
        "INFLUXDB_BUCKET",
        "GRAFANA_USER",
        "GRAFANA_PASSWORD",
    ],
}

_REQUIRED_FILES = {
    "iot": [
        "docker-compose.yml",
        ".env",
        "config/mosquitto/mosquitto.conf",
        "config/node-red/settings.js",
        "config/node-red/flows.json",
        "config/grafana/provisioning/datasources/datasources.yml",
        "scripts/init-buckets.sh",
    ],
}


def cmd() -> None:
    """Validate the current project's configuration and manifest."""
    manifest_path = mf.find()
    if manifest_path is None:
        console.print(
            "[red]✗[/red] No [bold].p4n4.json[/bold] found. "
            "Not inside a p4n4 project directory."
        )
        raise typer.Exit(1)

    project_dir = manifest_path.parent
    console.print(f"Validating project at [bold]{project_dir}[/bold] …\n")

    errors: list[str] = []

    # ── Manifest ──────────────────────────────────────────────────────────────
    try:
        data = mf.load(manifest_path)
    except Exception as exc:
        console.print(f"[red]✗[/red] .p4n4.json is not valid JSON: {exc}")
        raise typer.Exit(1) from exc

    if data.get("schema_version") != mf.SCHEMA_VERSION:
        errors.append(
            f".p4n4.json schema_version mismatch "
            f"(got {data.get('schema_version')}, expected {mf.SCHEMA_VERSION})"
        )
    else:
        console.print("[green]✓[/green] .p4n4.json — valid")

    layers: list[str] = data.get("layers", [])

    # ── Required files ────────────────────────────────────────────────────────
    for layer in layers:
        for rel in _REQUIRED_FILES.get(layer, []):
            path = project_dir / rel
            if not path.exists():
                errors.append(f"Missing file: {rel}")
            else:
                console.print(f"[green]✓[/green] {rel}")

    # ── .env keys ─────────────────────────────────────────────────────────────
    env_path = project_dir / ".env"
    if env_path.exists():
        env = envutil.load(env_path)
        for layer in layers:
            for key in _REQUIRED_ENV_KEYS.get(layer, []):
                if not env.get(key):
                    errors.append(f".env missing required key: {key}")
        if not errors:
            console.print("[green]✓[/green] .env — all required keys present")
    else:
        errors.append(".env file not found")

    # ── Result ────────────────────────────────────────────────────────────────
    if errors:
        console.print()
        for err in errors:
            console.print(f"[red]✗[/red] {err}")
        console.print(f"\n[red]Validation failed[/red] — {len(errors)} issue(s) found.")
        raise typer.Exit(1)
    else:
        console.print("\n[green]All checks passed.[/green]")
