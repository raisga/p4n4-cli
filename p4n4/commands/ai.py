"""p4n4 ai -- GenAI stack subcommands: System 1 (laya typed decisions)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from p4n4_lib import compose, layout, scaffold
from p4n4_lib import env as envutil
from p4n4_lib import secrets as secretutil
from p4n4_lib import system1 as s1
from p4n4_lib.layers import LAYERS
from rich.console import Console
from rich.table import Table

from p4n4.project import require_compose_dirs

app = typer.Typer(help="Manage the GenAI stack.", no_args_is_help=True)
system1_app = typer.Typer(
    help="System 1: fast typed decisions with laya (advisory routing, off by default).",
    no_args_is_help=True,
)
app.add_typer(system1_app, name="system1")
console = Console()

# specs §8.4: a validation error, here a question set failing its gates
EXIT_VALIDATION = 5
CONTAINER = "p4n4-system1"
N8N_CONTAINER = "p4n4-n8n"
# The Header Auth credentials the workflows refer to, by the .env key they hold: the one
# incident-escalation and operator-intake call System 1 with, and the one operator-intake's
# webhook checks channel adapters against
N8N_CREDENTIALS = {
    s1.API_KEY: ("p4n4-system1", "p4n4 System 1"),
    s1.INTAKE_TOKEN: ("p4n4-operator-intake", "p4n4 Operator Intake"),
}
LAST_EVAL = "config/system1/last-eval.json"
# Where Node-RED keeps feedback that carries its state (opt-in, see `feedback`)
FEEDBACK_DIR = "/data/system1/feedback"
HEALTH_TIMEOUT_S = 240
CHECKPOINTS = ("multilingual", "english")


def _ai_dir() -> Path:
    return require_compose_dirs("ai")[0][1]


def _iot_dir() -> Path | None:
    """The project's iot layer, if it has one (Node-RED's subflow needs the key too)."""
    return next((d for name, d in require_compose_dirs() if name == "iot"), None)


def _compose(ai_dir: Path, *args: str, **kw) -> subprocess.CompletedProcess:
    try:
        cmd = compose.compose_cmd()
    except compose.ComposeNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    return subprocess.run([*cmd, *args], cwd=ai_dir, check=False, **kw)


def _env(ai_dir: Path) -> dict[str, str]:
    path = ai_dir / envutil.ENV_FILE
    return envutil.load(path) if path.exists() else {}


def _container_state(name: str) -> tuple[str, str]:
    """(status, health) of a container; ("missing", "") when it doesn't exist."""
    fmt = "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}"
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", fmt, name],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "missing", ""
    if result.returncode != 0:
        return "missing", ""
    status, _, health = result.stdout.strip().partition(" ")
    return status, health


def _require_running() -> None:
    status, health = _container_state(CONTAINER)
    if status != "running" or health not in ("healthy", ""):
        console.print(
            f"[red]Error:[/red] System 1 isn't serving ({status}"
            f"{', ' + health if health else ''}). "
            "Start it with [bold]p4n4 ai system1 enable[/bold]."
        )
        raise typer.Exit(1)


def _client(ai_dir: Path, target: str, lines: list[str]) -> list[dict]:
    """Send one request per line through the in-container client (s1.CLIENT): the key never
    leaves the container and no host port is needed."""
    result = _compose(
        ai_dir,
        *("exec", "-T", s1.SERVICE, "python", "-c", s1.CLIENT, target),
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]Error:[/red] the System 1 client failed: {result.stderr.strip()}")
        raise typer.Exit(1)
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _load_sets(ai_dir: Path, name: str | None = None) -> list[s1.QuestionSet]:
    try:
        sets = s1.list_sets(ai_dir / s1.SETS_DIR)
    except s1.QuestionSetError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(EXIT_VALIDATION) from exc
    if name:
        sets = [s for s in sets if s.name == name]
        if not sets:
            console.print(
                f"[red]Error:[/red] No question set [bold]{name}[/bold] in {s1.SETS_DIR}."
            )
            raise typer.Exit(1)
    return sets


# ── n8n credential ───────────────────────────────────────────────────────────


def sync_n8n_credentials(ai_dir: Path, values: dict[str, str]) -> str:
    """
    Create or update the Header Auth credentials of N8N_CREDENTIALS for the .env keys in
    `values`. n8n encrypts them on import. Inside a running n8n they take effect at once;
    otherwise they're written to n8n's volume with a one-off container. Returns what happened,
    for the caller to print.
    """
    values = {k: v for k, v in values.items() if k in N8N_CREDENTIALS and v}
    if not values:
        return "skipped: no credential to update"
    if "n8n" not in s1.parse_profiles(_env(ai_dir).get("COMPOSE_PROFILES", "")):
        return "skipped: n8n isn't in COMPOSE_PROFILES (run this again after enabling it)"
    try:
        compose.compose_cmd()
    except compose.ComposeNotFoundError as exc:
        return f"failed: {exc}"
    credentials = [
        {
            "id": N8N_CREDENTIALS[env_key][0],
            "name": N8N_CREDENTIALS[env_key][1],
            "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": f"Bearer {value}"},
        }
        for env_key, value in values.items()
    ]
    # The keys reach the container on stdin, never in a command line
    script = (
        "umask 077; f=/tmp/p4n4-system1-credential.json; cat > $f && "
        "n8n import:credentials --input=$f >/dev/null; rc=$?; rm -f $f; exit $rc"
    )
    if _container_state(N8N_CONTAINER)[0] == "running":
        args = ["exec", "-T", "n8n", "sh", "-c", script]
    else:
        # A one-off n8n container joins p4n4-net like the service does
        try:
            compose.ensure_network(layout.NETWORK, layout.NETWORK_SUBNET)
        except compose.DockerError as exc:
            return f"failed: {exc}"
        args = ["run", "--rm", "--no-deps", "-T", "--entrypoint", "sh", "n8n", "-c", script]
    result = _compose(ai_dir, *args, input=json.dumps(credentials), capture_output=True, text=True)
    if result.returncode != 0:
        return f"failed: {(result.stderr or result.stdout).strip()[-300:]}"
    return f"updated ({', '.join(c['name'] for c in credentials)})"


# ── Commands ─────────────────────────────────────────────────────────────────


def _copy_default_sets(ai_dir: Path, source: str | None) -> list[str]:
    """Copy the ai stack's shipped sets (and their evaluation files) that the project lacks."""
    src, tmpdir = scaffold.fetch_source(LAYERS["ai"], source)
    try:
        shipped = src / s1.SETS_DIR
        dest = ai_dir / s1.SETS_DIR
        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for f in sorted(shipped.glob("*")) if shipped.is_dir() else []:
            if f.is_file() and not (dest / f.name).exists():
                shutil.copy2(f, dest / f.name)
                copied.append(f.name)
        return copied
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _wait_healthy() -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    with console.status("Waiting for System 1 to load the model…"):
        while time.monotonic() < deadline:
            status, health = _container_state(CONTAINER)
            if health == "healthy":
                return True
            if status in ("exited", "dead"):
                return False
            time.sleep(2)
    return False


@system1_app.command("enable")
def enable(
    checkpoint: Annotated[
        str | None,
        typer.Option(help="Checkpoint to serve: multilingual (default) or english."),
    ] = None,
    no_pull: Annotated[
        bool, typer.Option("--no-pull", help="Don't download the model or start the service.")
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source-ai",
            help="Local p4n4-ai checkout to copy missing default question sets from.",
        ),
    ] = None,
) -> None:
    """Turn System 1 on: profile, keys, question sets, n8n credentials, model, service."""
    if checkpoint is not None and checkpoint not in CHECKPOINTS:
        console.print(f"[red]Error:[/red] --checkpoint must be one of {', '.join(CHECKPOINTS)}.")
        raise typer.Exit(1)
    ai_dir = _ai_dir()
    env_path = ai_dir / envutil.ENV_FILE
    env = _env(ai_dir)

    envutil.set_value(env_path, "COMPOSE_PROFILES", s1.add_profile(env.get("COMPOSE_PROFILES", "")))
    key = env.get(s1.API_KEY, "")
    if len(key) < s1.MIN_API_KEY_LENGTH:
        key = secretutil.token()
        envutil.set_value(
            env_path, s1.API_KEY, key, comment="System 1 bearer token for callers (n8n, Node-RED)"
        )
        console.print(f"[green]✓[/green] Generated {s1.API_KEY}")
    intake = env.get(s1.INTAKE_TOKEN, "")
    if len(intake) < s1.MIN_API_KEY_LENGTH:
        intake = secretutil.token()
        envutil.set_value(
            env_path,
            s1.INTAKE_TOKEN,
            intake,
            comment="Bearer token channel adapters send to n8n's operator-intake webhook",
        )
        console.print(f"[green]✓[/green] Generated {s1.INTAKE_TOKEN}")
    iot_dir = _iot_dir()
    if iot_dir is not None:
        iot_env = iot_dir / envutil.ENV_FILE
        if (envutil.load(iot_env) if iot_env.exists() else {}).get(s1.API_KEY) != key:
            envutil.set_value(
                iot_env, s1.API_KEY, key, comment="The p4n4-system1 subflow's bearer token"
            )
            console.print(
                f"[green]✓[/green] {s1.API_KEY} copied to the iot layer for Node-RED "
                "[dim](restart it with p4n4 up)[/dim]"
            )
    if checkpoint:
        envutil.set_value(env_path, "SYSTEM1_CHECKPOINT", checkpoint)
    console.print(f"[green]✓[/green] {s1.PROFILE} added to COMPOSE_PROFILES")

    try:
        copied = _copy_default_sets(ai_dir, source)
    except scaffold.ScaffoldError as exc:
        console.print(f"[yellow]Couldn't fetch the default question sets:[/yellow] {exc}")
        copied = []
    if copied:
        console.print(f"[green]✓[/green] Copied default question sets: {', '.join(copied)}")
    sets = _load_sets(ai_dir)
    if not sets:
        console.print(
            f"[yellow]No question sets in {s1.SETS_DIR}: the service will serve none.[/yellow]"
        )

    credentials = sync_n8n_credentials(ai_dir, {s1.API_KEY: key, s1.INTAKE_TOKEN: intake})
    console.print(f"  n8n credentials: {credentials}")

    if no_pull:
        console.print("\nRun [bold]p4n4 ai system1 pull[/bold], then [bold]p4n4 up[/bold].")
        return

    _pull(ai_dir)
    try:
        compose.ensure_network(layout.NETWORK, layout.NETWORK_SUBNET)
    except compose.DockerError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    if _compose(ai_dir, "up", "-d", s1.SERVICE).returncode != 0:
        raise typer.Exit(1)
    if not _wait_healthy():
        console.print("[red]Error:[/red] System 1 didn't become healthy. Its last log lines:")
        _compose(ai_dir, "logs", "--tail", "15", s1.SERVICE)
        raise typer.Exit(1)
    console.print(
        f"[green]✓[/green] System 1 is serving {', '.join(f'{s.name} v{s.version}' for s in sets)} "
        "at http://p4n4-system1:8000 (p4n4-net only)"
    )
    console.print(
        "[dim]Suggestions are advisory: rules route first, and every alert is still escalated. "
        "Check a set on your own examples with[/dim] p4n4 ai system1 eval"
    )


def _volume_name(ai_dir: Path) -> str | None:
    result = _compose(ai_dir, "config", "--format", "json", capture_output=True, text=True)
    if result.returncode != 0:
        return None
    volume = (json.loads(result.stdout).get("volumes") or {}).get("system1-models") or {}
    return volume.get("name")


@system1_app.command("disable")
def disable(
    purge: Annotated[
        bool, typer.Option("--purge", help="Also delete the downloaded model (asks first).")
    ] = False,
) -> None:
    """Turn System 1 off: drop the profile and stop the service. The key stays in .env."""
    ai_dir = _ai_dir()
    env = _env(ai_dir)
    volume = _volume_name(ai_dir) if purge else None
    envutil.set_value(
        ai_dir / envutil.ENV_FILE,
        "COMPOSE_PROFILES",
        s1.remove_profile(env.get("COMPOSE_PROFILES", "")),
    )
    console.print(f"[green]✓[/green] {s1.PROFILE} removed from COMPOSE_PROFILES")
    _compose(ai_dir, "--profile", s1.PROFILE, "rm", "--stop", "--force", s1.SERVICE)
    console.print("[green]✓[/green] System 1 stopped")
    if purge and volume:
        if typer.confirm(f"Delete the model volume {volume}?", default=False):
            result = subprocess.run(
                ["docker", "volume", "rm", volume], capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                console.print(f"[green]✓[/green] Deleted {volume}")
            else:
                console.print(f"[red]Error:[/red] {result.stderr.strip()}")
                raise typer.Exit(1)


def _pull(ai_dir: Path) -> None:
    console.print("Downloading the pinned checkpoint (about 650 MB the first time)…")
    if _compose(ai_dir, "run", "--rm", s1.PULL_SERVICE).returncode != 0:
        console.print("[red]Error:[/red] the pull failed; see the output above.")
        raise typer.Exit(1)


@system1_app.command("pull")
def pull() -> None:
    """Download the pinned checkpoint and check it against the image's hashes."""
    _pull(_ai_dir())


@system1_app.command("status")
def status() -> None:
    """Show health, checkpoint, revision, question sets and the last evaluation."""
    ai_dir = _ai_dir()
    env = _env(ai_dir)
    state, health = _container_state(CONTAINER)
    enabled = s1.PROFILE in s1.parse_profiles(env.get("COMPOSE_PROFILES", ""))
    last = {}
    if (ai_dir / LAST_EVAL).exists():
        last = json.loads((ai_dir / LAST_EVAL).read_text(encoding="utf-8"))

    colour = "green" if health == "healthy" else "red" if state == "running" else "dim"
    console.print(
        f"System 1: [{colour}]{state}{' (' + health + ')' if health else ''}[/{colour}]"
        f"  profile {'[green]enabled[/green]' if enabled else '[dim]disabled[/dim]'}"
    )
    console.print(
        f"  checkpoint {env.get('SYSTEM1_CHECKPOINT') or 'multilingual'}, revision "
        f"{(env.get('SYSTEM1_REVISION') or 'aa8c91ca088ec597df95a0d1c76b3063cb2ae5e8')[:12]}, "
        f"image {env.get('SYSTEM1_IMAGE') or 'ghcr.io/raisga/p4n4-system1:0.1.0'}"
    )
    sets = _load_sets(ai_dir)
    if not sets:
        console.print(f"  [yellow]No question sets in {s1.SETS_DIR}[/yellow]")
        return
    served = _served_versions(ai_dir) if state == "running" and health == "healthy" else None
    stale: list[str] = []
    table = Table(show_header=True)
    for col in ("Set", "Version", "Thresholds", "Examples", "Last evaluation"):
        table.add_column(col)
    for qset in sets:
        try:
            n = len(s1.load_examples(qset))
        except s1.QuestionSetError:
            n = 0
        run = last.get(qset.name)
        if not run:
            verdict = "[dim]never[/dim]"
        elif run["version"] != qset.version:
            verdict = f"[yellow]v{run['version']} (set is v{qset.version}: run eval)[/yellow]"
        else:
            verdict = ("[green]passed[/green]" if run["passed"] else "[red]failed[/red]") + (
                f" [dim]{run['ts']}[/dim]"
            )
        version = str(qset.version)
        if served is not None and served.get(qset.name) != qset.version:
            version += "*"
            stale.append(
                f"{qset.name} (serving v{served[qset.name]})"
                if qset.name in served
                else f"{qset.name} (not served)"
            )
        table.add_row(
            qset.name,
            version,
            ", ".join(f"{q} {t:g}" for q, t in qset.thresholds.items()) or "-",
            str(n),
            verdict,
        )
    console.print(table)
    if stale:
        console.print(
            f"[yellow]* The service loaded an older copy at start-up: {', '.join(stale)}. "
            "Restart it to serve the files: p4n4 up[/yellow]"
        )


def _served_versions(ai_dir: Path) -> dict[str, int] | None:
    """{set: version} the running service loaded at start-up (GET /v1/sets), None if unknown."""
    try:
        [reply] = _client(ai_dir, s1.LIST_SETS, [])
    except (typer.Exit, ValueError):
        return None
    if reply.get("status") != 200:
        return None
    return {s["name"]: s["version"] for s in reply["body"].get("sets", [])}


@system1_app.command("decide")
def decide(
    set_name: Annotated[str, typer.Argument(metavar="SET", help="Question set to run.")],
    state: Annotated[
        str, typer.Option("--state", help="JSON file holding the state, or - for stdin.")
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Print the raw response.")] = False,
) -> None:
    """Run a question set on one state and print the answers."""
    ai_dir = _ai_dir()
    _load_sets(ai_dir, set_name)
    try:
        text = sys.stdin.read() if state == "-" else Path(state).read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Error:[/red] Couldn't read a JSON state: {exc}")
        raise typer.Exit(1) from exc
    _require_running()
    [reply] = _client(ai_dir, set_name, [json.dumps(value)])
    if reply["status"] != 200:
        detail = reply["body"].get("detail", reply["body"])
        console.print(f"[red]Error:[/red] System 1 answered {reply['status']}: {detail}")
        raise typer.Exit(1)
    body = reply["body"]
    if as_json:
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return
    table = Table(title=f"{set_name} v{body['set']['version']} ({reply['latency_ms']:.0f} ms)")
    for col in ("Question", "Choice", "Confidence", "Top probability", "Use"):
        table.add_column(col)
    for qid, a in body["answers"].items():
        table.add_row(
            qid,
            a["choice"],
            f"{a['confidence']:.2f}",
            f"{a.get('answer_confidence', max(a['probabilities'].values())):.2f}",
            "[dim]abstain[/dim]" if a["abstain"] else "[green]yes[/green]",
        )
    console.print(table)


def _print_report(report: s1.Report) -> None:
    for q in report.questions:
        m = q.metrics
        table = Table(title=f"{report.set} v{report.version} · {q.question}", show_header=True)
        for col in ("Metric", "Value", "Gate"):
            table.add_column(col)
        g = q.gates
        table.add_row("Coverage", f"{m.coverage:.2f}", f"≥ {g['min_coverage']:.2f}")
        table.add_row(
            "Answered accuracy", f"{m.answered_accuracy:.2f}", f"≥ {g['min_answered_accuracy']:.2f}"
        )
        table.add_row(
            "Confident-wrong rate", f"{m.confident_wrong:.3f}", f"≤ {g['max_confident_wrong']:.3f}"
        )
        table.add_row("Abstained on null examples", f"{m.null_abstention:.2f}", "")
        table.add_row("Examples (keyed / null)", f"{m.n1} / {m.n0}", "")
        console.print(table)
        if len(q.by_source) > 1:
            for source, sm in q.by_source.items():
                # Coverage and accuracy are undefined without keyed examples (an edge-only source)
                keyed = (
                    f"coverage {sm.coverage:.2f}, accuracy {sm.answered_accuracy:.2f}"
                    if sm.n1
                    else "no keyed examples"
                )
                console.print(
                    f"  [dim]{source or '(no source)'}:[/dim] {keyed}, "
                    f"confident-wrong {sm.confident_wrong:.3f}"
                )
        for lang, lm in q.by_lang.items():
            console.print(
                f"  [dim]language {lang}:[/dim] coverage {lm.coverage:.2f}, accuracy "
                f"{lm.answered_accuracy:.2f}, confident-wrong {lm.confident_wrong:.3f} "
                f"[dim]({lm.n1} keyed / {lm.n0} null)[/dim]"
            )
        answers = sorted({a for row in q.confusion.values() for a in row})
        confusion = Table(title="Expected → answered", show_header=True)
        confusion.add_column("")
        for a in answers:
            confusion.add_column(a)
        for expected, row in q.confusion.items():
            confusion.add_row(expected, *(str(row.get(a, "")) for a in answers))
        console.print(confusion)
    lat = report.latency_ms
    console.print(f"Latency p50 {lat['p50']:.0f} ms, p95 {lat['p95']:.0f} ms")


@system1_app.command("eval")
def eval_(
    set_name: Annotated[
        str | None, typer.Argument(metavar="[SET]", help="Set to evaluate (default: all).")
    ] = None,
    no_gates: Annotated[
        bool, typer.Option("--no-gates", help="Print the metrics without enforcing gates.")
    ] = False,
    fit_thresholds: Annotated[
        bool,
        typer.Option("--fit-thresholds", help="Propose thresholds per question (never written)."),
    ] = False,
    fit_calibration: Annotated[
        bool,
        typer.Option(
            "--fit-calibration",
            help="Propose temperatures per laya bucket and per question (never written).",
        ),
    ] = False,
) -> None:
    """Run each set's <name>.eval.jsonl through System 1 and check its gates (exit 5 on fail)."""
    ai_dir = _ai_dir()
    sets = _load_sets(ai_dir, set_name)
    if not sets:
        console.print(f"[yellow]No question sets in {s1.SETS_DIR}.[/yellow]")
        raise typer.Exit(1)
    loaded = []
    for qset in sets:
        try:
            loaded.append((qset, s1.load_examples(qset)))
        except s1.QuestionSetError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(EXIT_VALIDATION) from exc
    _require_running()

    failed, runs, fitted = False, {}, []
    for qset, examples in loaded:
        with console.status(f"Running {len(examples)} examples of {qset.name}…"):
            replies = _client(ai_dir, qset.name, [json.dumps(ex.state) for ex in examples])
        errors = [(ex, r) for ex, r in zip(examples, replies, strict=True) if r["status"] != 200]
        if errors:
            for ex, r in errors[:5]:
                detail = r["body"].get("detail", r["body"]) if isinstance(r["body"], dict) else ""
                console.print(f"[red]Error:[/red] line {ex.line}: {r['status']} {detail}")
            raise typer.Exit(EXIT_VALIDATION)
        answers = [r["body"]["answers"] for r in replies]
        report = s1.evaluate(
            qset, examples, answers, [r["latency_ms"] for r in replies], gates=not no_gates
        )
        _print_report(report)
        if report.failures:
            failed = True
            for f in report.failures:
                console.print(f"[red]✗[/red] {f}")
        elif not no_gates:
            console.print(f"[green]✓[/green] {qset.name} v{qset.version} passes its gates")
        runs[qset.name] = {
            "version": qset.version,
            "passed": report.passed,
            "gated": not no_gates,
            "ts": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "report": report.as_dict(),
        }
        if fit_thresholds:
            console.print(
                f"\n[bold]Proposed thresholds for {qset.name}[/bold] [dim](fitted on "
                "two thirds, checked on the held-out third; edit the set and bump its "
                "version to apply)[/dim]"
            )
            for qid, metrics in s1.fit_thresholds(qset, examples, answers).items():
                for on, fit in metrics.items():
                    if fit.get("threshold") is None:
                        console.print(f"  {qid} on {on}: no threshold meets the gates")
                        continue
                    held = fit["held_out"]
                    console.print(
                        f"  {qid} on {on}: [bold]{fit['threshold']}[/bold] → held-out coverage "
                        f"{held['coverage']:.2f}, accuracy {held['answered_accuracy']:.2f}, "
                        f"confident-wrong {held['confident_wrong']:.3f}"
                    )
        fitted.append((qset, examples, answers))

    if fit_calibration:
        console.print(
            "\n[bold]Proposed temperatures[/bold] [dim](per laya bucket, shared by "
            "every set; calibrate before fitting thresholds)[/dim]"
        )
        for bucket, fit in s1.fit_calibration(fitted).items():
            console.print(
                f"  {bucket}: T = [bold]{fit['temperature']}[/bold] over {fit['n']} examples "
                f"(NLL {fit['nll_at_1']} → {fit['nll']})"
            )
        console.print(
            "[bold]Or per question[/bold] [dim](a set's `temperatures` key, applied in place of "
            "its bucket's; bump the set's version)[/dim]"
        )
        for qset, examples, answers in fitted:
            fits = s1.fit_question_temperatures(qset, examples, answers)
            for qid, fit in fits.items():
                console.print(
                    f"  {qset.name}.{qid}: T = [bold]{fit['temperature']}[/bold] over "
                    f"{fit['n']} examples (NLL {fit['nll_at_1']} → {fit['nll']})"
                )

    if not no_gates:
        path = ai_dir / LAST_EVAL
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        path.write_text(json.dumps({**previous, **runs}, indent=2) + "\n", encoding="utf-8")
    if failed:
        raise typer.Exit(EXIT_VALIDATION)


@system1_app.command("feedback")
def feedback(
    set_name: Annotated[str, typer.Argument(metavar="SET", help="Question set.")],
    append: Annotated[
        bool,
        typer.Option("--append", help="Append the new lines to the set's evaluation file."),
    ] = False,
) -> None:
    """
    Turn confirmations Node-RED kept (FEEDBACK_STATES in n8n's Operator Intake) into evaluation
    lines with source "feedback". Prints them unless --append; redact names before appending.
    """
    ai_dir = _ai_dir()
    [qset] = _load_sets(ai_dir, set_name)
    iot_dir = _iot_dir()
    if iot_dir is None:
        console.print(
            "[red]Error:[/red] Feedback is kept by Node-RED: this project has no iot layer."
        )
        raise typer.Exit(1)
    result = _compose(
        iot_dir,
        *("exec", "-T", "node-red", "cat", f"{FEEDBACK_DIR}/{qset.name}.jsonl"),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(
            f"[yellow]No kept feedback for {qset.name}.[/yellow] [dim]Node-RED keeps it only when "
            "n8n's Operator Intake sets FEEDBACK_STATES, and it must be running.[/dim]"
        )
        raise typer.Exit(1)
    messages = []
    for raw in result.stdout.splitlines():
        try:
            messages.append(json.loads(raw))
        except ValueError:
            continue
    lines = s1.feedback_examples(qset, messages)
    path = qset.eval_path
    known = set()
    if path is not None and path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                known.add(json.loads(raw).get("id"))
            except (ValueError, AttributeError):
                continue
    new = [line for line in lines if line["id"] not in known]
    if not append:
        for line in new:
            print(json.dumps(line, ensure_ascii=False))
        Console(stderr=True).print(
            f"[dim]{len(new)} new of {len(lines)} kept examples for {qset.name}; "
            "add them with --append.[/dim]",
            highlight=False,
        )
        return
    if new:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        text += "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in new)
        path.write_text(text, encoding="utf-8")
    console.print(
        f"[green]✓[/green] Appended {len(new)} examples to {path.name} "
        f"({len(lines) - len(new)} were already there). Run [bold]p4n4 ai system1 eval "
        f"{qset.name}[/bold] next."
    )
