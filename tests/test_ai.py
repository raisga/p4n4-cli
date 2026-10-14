"""Tests: p4n4 ai system1 commands, with Docker replaced by fakes."""

from __future__ import annotations

import json
import os
import shutil

import pytest
from p4n4_lib import env as envutil
from p4n4_lib import system1 as s1

from p4n4.cli import app
from p4n4.commands import ai
from tests.test_cli import _AI_SOURCE, _IOT_SOURCE, _run_in, runner

SETS = s1.SETS_DIR


@pytest.fixture()
def ai_project(tmp_path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    result = runner.invoke(
        app, ["init", "proj-ai", "--layer", "ai", "--no-interactive", "--source-ai", _AI_SOURCE]
    )
    assert result.exit_code == 0, result.output
    yield tmp_path / "proj-ai"
    os.chdir(old_cwd)


@pytest.fixture()
def iot_ai_project(tmp_path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "init",
            "proj-both",
            "--layer",
            "iot,ai",
            "--no-interactive",
            "--source-iot",
            _IOT_SOURCE,
            "--source-ai",
            _AI_SOURCE,
        ],
    )
    assert result.exit_code == 0, result.output
    yield tmp_path / "proj-both"
    os.chdir(old_cwd)


@pytest.fixture()
def docker(monkeypatch):
    """Record compose calls; containers report what `states` says (default: missing)."""
    calls, states = [], {}

    class Done:
        returncode, stdout, stderr = 0, "", ""

    def fake_compose(ai_dir, *args, **kw):
        calls.append((args, kw.get("input")))
        return Done()

    monkeypatch.setattr(ai, "_compose", fake_compose)
    monkeypatch.setattr(ai, "_container_state", lambda name: states.get(name, ("missing", "")))
    return calls, states


def _serving(states):
    states[ai.CONTAINER] = ("running", "healthy")


def _intake_expected():
    """text -> {question: expected}, from the shipped operator-intake evaluation file."""
    path = __import__("pathlib").Path(_AI_SOURCE) / SETS / "operator-intake.eval.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {r["state"]["text"]: r["expect"] for r in rows}


def _intake_right(state):
    """A perfect operator-intake answer: the expected key, or a confident no-answer key."""
    expected = _intake_expected()[state["text"]]
    no_answer = {"intent": "other", "asset": "pump"}
    return {q: _cause(expected[q] or no_answer[q], 0.97) for q in ("intent", "asset")}


def _fake_client(monkeypatch, answer, intake=_intake_right, served=None):
    """Answer incident-triage with answer(state) as its `cause` answer, operator-intake with
    intake(state), and GET /v1/sets with the `served` {set: version}."""
    sent = []

    def client(ai_dir, target, lines):
        sent.append((target, lines))
        if target == s1.LIST_SETS:
            sets = [{"name": k, "version": v} for k, v in (served or {}).items()]
            return [{"status": 200, "latency_ms": 1.0, "body": {"sets": sets}}]
        replies = []
        for line in lines:
            state = json.loads(line)
            answers = intake(state) if target == "operator-intake" else {"cause": answer(state)}
            replies.append(
                {
                    "status": 200,
                    "latency_ms": 12.0,
                    "body": {"set": {"name": target, "version": 3}, "answers": answers},
                }
            )
        return replies

    monkeypatch.setattr(ai, "_client", client)
    return sent


def _cause(choice, confidence, threshold=0.9):
    return {
        "choice": choice,
        "confidence": confidence,
        "answer_confidence": confidence,
        "abstain": confidence < threshold,
        "probabilities": {choice: confidence},
    }


def _expected(ai_project):
    """alert -> expected cause, from the shipped evaluation file."""
    path = ai_project / SETS / "incident-triage.eval.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {r["state"]["alert"]: r["expect"]["cause"] for r in rows}


# ── init and secrets ─────────────────────────────────────────────────────────


def test_init_ai_generates_the_system1_key_and_ships_the_sets(ai_project):
    env = envutil.load(ai_project / ".env")
    assert len(env["SYSTEM1_API_KEY"]) == 64
    assert "system1" not in env["COMPOSE_PROFILES"]
    assert (ai_project / SETS / "incident-triage.json").is_file()
    assert (ai_project / SETS / "incident-triage.eval.jsonl").is_file()


def test_secret_rotate_updates_the_n8n_credential(ai_project, monkeypatch):
    synced = []
    monkeypatch.setattr(
        ai, "sync_n8n_credentials", lambda d, values: synced.append(values) or "updated"
    )
    before = envutil.load(ai_project / ".env")
    result = _run_in(ai_project, ["secret", "rotate"], input="y\n", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    after = envutil.load(ai_project / ".env")
    keys = ("SYSTEM1_API_KEY", "OPERATOR_INTAKE_TOKEN", "SYSTEM1_ALERT_TOKEN")
    for key in keys:
        assert after[key] != before[key]
    assert synced == [{k: after[k] for k in keys}]
    assert "n8n credentials: updated" in result.output


def test_init_shares_the_system1_key_with_the_iot_layer(iot_ai_project):
    ai_env = envutil.load(iot_ai_project / "ai" / ".env")
    iot_env = envutil.load(iot_ai_project / "iot" / ".env")
    assert len(ai_env["OPERATOR_INTAKE_TOKEN"]) == 64
    assert iot_env["SYSTEM1_API_KEY"] == ai_env["SYSTEM1_API_KEY"]
    assert len(ai_env["SYSTEM1_ALERT_TOKEN"]) == 64
    assert iot_env["SYSTEM1_ALERT_TOKEN"] == ai_env["SYSTEM1_ALERT_TOKEN"]
    assert "OPERATOR_INTAKE_TOKEN" not in iot_env


def test_secret_rotate_keeps_both_copies_of_the_system1_key(iot_ai_project, monkeypatch):
    monkeypatch.setattr(ai, "sync_n8n_credentials", lambda d, values: "updated")
    result = _run_in(iot_ai_project, ["secret", "rotate"], input="y\n", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    ai_env = envutil.load(iot_ai_project / "ai" / ".env")
    iot_env = envutil.load(iot_ai_project / "iot" / ".env")
    assert iot_env["SYSTEM1_API_KEY"] == ai_env["SYSTEM1_API_KEY"]


def test_credential_sync_skips_without_n8n(ai_project, docker):
    calls, _ = docker
    assert ai.sync_n8n_credentials(ai_project, {"SYSTEM1_API_KEY": "k" * 64}).startswith("skipped")
    assert calls == []


def test_credential_goes_to_running_n8n_on_stdin(ai_project, docker):
    calls, states = docker
    envutil.set_value(ai_project / ".env", "COMPOSE_PROFILES", "ollama,n8n")
    states[ai.N8N_CONTAINER] = ("running", "healthy")
    values = {"SYSTEM1_API_KEY": "k" * 64, "OPERATOR_INTAKE_TOKEN": "t" * 64, "OTHER": "x"}
    result = ai.sync_n8n_credentials(ai_project, values)
    assert result == "updated (p4n4 System 1, p4n4 Operator Intake)"
    [(args, stdin)] = calls
    assert args[:3] == ("exec", "-T", "n8n")
    assert "k" * 64 not in " ".join(args)
    system1, intake = json.loads(stdin)
    assert system1["id"] == "p4n4-system1" and system1["type"] == "httpHeaderAuth"
    assert system1["data"] == {"name": "Authorization", "value": "Bearer " + "k" * 64}
    assert intake["id"] == "p4n4-operator-intake"
    assert intake["data"] == {"name": "Authorization", "value": "Bearer " + "t" * 64}


def test_credential_uses_a_one_off_n8n_when_stopped(ai_project, docker, monkeypatch):
    calls, _ = docker
    monkeypatch.setattr(ai.compose, "ensure_network", lambda *a: False)
    envutil.set_value(ai_project / ".env", "COMPOSE_PROFILES", "ollama,n8n")
    ai.sync_n8n_credentials(ai_project, {"SYSTEM1_API_KEY": "k" * 64})
    assert calls[0][0][:3] == ("run", "--rm", "--no-deps")


# ── enable / disable ─────────────────────────────────────────────────────────


def test_enable_no_pull_sets_profile_and_keeps_the_key(ai_project, docker):
    key = envutil.load(ai_project / ".env")["SYSTEM1_API_KEY"]
    result = _run_in(
        ai_project, ["ai", "system1", "enable", "--no-pull", "--source-ai", _AI_SOURCE]
    )
    assert result.exit_code == 0, result.output
    env = envutil.load(ai_project / ".env")
    assert env["COMPOSE_PROFILES"] == "ollama,system1"
    assert env["SYSTEM1_API_KEY"] == key
    assert docker[0] == []  # nothing started


def test_enable_on_an_older_project_adds_key_and_sets(ai_project, docker):
    env_path = ai_project / ".env"
    lines = [
        ln
        for ln in env_path.read_text().splitlines()
        if not ln.startswith(("SYSTEM1_", "OPERATOR_INTAKE_TOKEN"))
    ]
    env_path.write_text("\n".join(lines) + "\n")
    for f in (ai_project / SETS).iterdir():
        f.unlink()
    shutil.rmtree(ai_project / ai.CALIBRATION_DIR, ignore_errors=True)
    result = _run_in(
        ai_project,
        [
            "ai",
            "system1",
            "enable",
            "--no-pull",
            "--checkpoint",
            "english",
            "--source-ai",
            _AI_SOURCE,
        ],
    )
    assert result.exit_code == 0, result.output
    env = envutil.load(env_path)
    assert len(env["SYSTEM1_API_KEY"]) == 64
    assert len(env["OPERATOR_INTAKE_TOKEN"]) == 64
    assert env["SYSTEM1_CHECKPOINT"] == "english"
    assert "incident-triage.json" in result.output
    assert (ai_project / SETS / "incident-triage.eval.jsonl").is_file()
    # Ours before Compose mounts it, or Docker creates it as root
    assert (ai_project / ai.CALIBRATION_DIR).is_dir()


def test_enable_rejects_unknown_checkpoint(ai_project, docker):
    result = _run_in(ai_project, ["ai", "system1", "enable", "--checkpoint", "typed-decisions"])
    assert result.exit_code == 1 and "must be one of" in result.output


def test_enable_pulls_starts_and_waits(ai_project, docker, monkeypatch):
    calls, states = docker
    monkeypatch.setattr(ai.compose, "ensure_network", lambda *a: False)
    monkeypatch.setattr(ai, "_wait_healthy", lambda: True)
    result = _run_in(ai_project, ["ai", "system1", "enable", "--source-ai", _AI_SOURCE])
    assert result.exit_code == 0, result.output
    assert [c[0] for c in calls] == [("run", "--rm", "system1-pull"), ("up", "-d", "system1")]
    assert "incident-triage v3" in result.output


def test_enable_reports_an_unhealthy_service(ai_project, docker, monkeypatch):
    calls, _ = docker
    monkeypatch.setattr(ai.compose, "ensure_network", lambda *a: False)
    monkeypatch.setattr(ai, "_wait_healthy", lambda: False)
    result = _run_in(ai_project, ["ai", "system1", "enable", "--source-ai", _AI_SOURCE])
    assert result.exit_code == 1
    assert calls[-1][0][0] == "logs"


def test_disable_removes_the_profile(ai_project, docker):
    envutil.set_value(ai_project / ".env", "COMPOSE_PROFILES", "ollama,system1,n8n")
    result = _run_in(ai_project, ["ai", "system1", "disable"])
    assert result.exit_code == 0, result.output
    assert envutil.load(ai_project / ".env")["COMPOSE_PROFILES"] == "ollama,n8n"
    assert docker[0][-1][0] == ("--profile", "system1", "rm", "--stop", "--force", "system1")


# ── decide / eval / status ───────────────────────────────────────────────────


def test_decide_needs_a_running_service(ai_project, docker, tmp_path):
    state = tmp_path / "state.json"
    state.write_text('{"alert": "Smoke in cabinet 3"}')
    result = _run_in(
        ai_project, ["ai", "system1", "decide", "incident-triage", "--state", str(state)]
    )
    assert result.exit_code == 1 and "isn't serving" in result.output


def test_decide_prints_answers(ai_project, docker, monkeypatch, tmp_path):
    _serving(docker[1])
    sent = _fake_client(monkeypatch, lambda state: _cause("electrical", 0.99))
    state = tmp_path / "state.json"
    state.write_text('{"alert": "Smoke in cabinet 3"}')
    result = _run_in(
        ai_project, ["ai", "system1", "decide", "incident-triage", "--state", str(state)]
    )
    assert result.exit_code == 0, result.output
    assert "electrical" in result.output and "0.99" in result.output
    assert sent == [("incident-triage", ['{"alert": "Smoke in cabinet 3"}'])]


def test_decide_reads_stdin_and_prints_json(ai_project, docker, monkeypatch):
    _serving(docker[1])
    _fake_client(monkeypatch, lambda state: _cause("thermal", 0.4))
    result = _run_in(
        ai_project,
        ["ai", "system1", "decide", "incident-triage", "--state", "-", "--json"],
        input='{"alert": "Oil at 92 C"}',
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["answers"]["cause"]["abstain"] is True


def test_decide_unknown_set(ai_project, docker):
    result = _run_in(ai_project, ["ai", "system1", "decide", "nope", "--state", "-"], input="{}")
    assert result.exit_code == 1 and "No question set" in result.output


def test_eval_passes_and_records_the_run(ai_project, docker, monkeypatch):
    _serving(docker[1])
    expected = _expected(ai_project)
    _fake_client(
        monkeypatch,
        lambda state: (
            _cause(expected[state["alert"]], 0.97)
            if expected[state["alert"]]
            else _cause("unknown", 0.95)
        ),
    )
    result = _run_in(ai_project, ["ai", "system1", "eval", "--fit-thresholds"])
    assert result.exit_code == 0, result.output
    assert "passes its gates" in result.output and "Proposed thresholds" in result.output
    last = json.loads((ai_project / ai.LAST_EVAL).read_text())
    assert last["incident-triage"]["passed"] is True and last["incident-triage"]["version"] == 3
    assert last["operator-intake"]["passed"] is True
    assert "language es:" in result.output
    status = _run_in(ai_project, ["ai", "system1", "status"])
    assert "passed" in status.output and "incident-triage" in status.output


def test_status_says_when_the_service_serves_an_older_set(ai_project, docker, monkeypatch):
    _serving(docker[1])
    _fake_client(monkeypatch, lambda s: None, served={"incident-triage": 2})
    result = _run_in(ai_project, ["ai", "system1", "status"])
    assert result.exit_code == 0, result.output
    assert "incident-triage (serving v2)" in result.output
    assert "operator-intake (not served)" in result.output


def test_eval_exits_5_when_a_gate_fails(ai_project, docker, monkeypatch):
    _serving(docker[1])
    _fake_client(monkeypatch, lambda state: _cause("electrical", 0.99))
    result = _run_in(ai_project, ["ai", "system1", "eval", "incident-triage"])
    assert result.exit_code == ai.EXIT_VALIDATION
    assert "confident-wrong rate" in result.output
    assert json.loads((ai_project / ai.LAST_EVAL).read_text())["incident-triage"]["passed"] is False


def test_eval_no_gates_prints_but_passes(ai_project, docker, monkeypatch):
    _serving(docker[1])
    _fake_client(monkeypatch, lambda state: _cause("electrical", 0.99))
    result = _run_in(ai_project, ["ai", "system1", "eval", "--no-gates", "--fit-calibration"])
    assert result.exit_code == 0, result.output
    assert "Proposed temperatures" in result.output and "choice:6-10" in result.output
    assert "Or per question" in result.output and "operator-intake.asset: T =" in result.output
    assert not (ai_project / ai.LAST_EVAL).exists()


def test_eval_service_errors_are_validation_errors(ai_project, docker, monkeypatch):
    _serving(docker[1])

    def client(ai_dir, target, lines):
        return [{"status": 422, "latency_ms": 1, "body": {"detail": "state is 900 tokens"}}] * len(
            lines
        )

    monkeypatch.setattr(ai, "_client", client)
    result = _run_in(ai_project, ["ai", "system1", "eval"])
    assert result.exit_code == ai.EXIT_VALIDATION and "state is 900 tokens" in result.output


def test_status_without_a_service(ai_project, docker):
    result = _run_in(ai_project, ["ai", "system1", "status"])
    assert result.exit_code == 0, result.output
    assert "missing" in result.output and "never" in result.output


def test_status_names_a_fine_tuned_repository(ai_project, docker):
    envutil.set_value(ai_project / ".env", "SYSTEM1_REPO", "example/p4n4-laya")
    result = _run_in(ai_project, ["ai", "system1", "status"])
    assert result.exit_code == 0, result.output
    assert "multilingual from example/p4n4-laya" in result.output


# ── enable with an iot layer, feedback ──────────────────────────────────────


def test_enable_copies_the_key_to_the_iot_layer(iot_ai_project, docker):
    iot_env = iot_ai_project / "iot" / ".env"
    envutil.set_value(iot_env, "SYSTEM1_API_KEY", "")
    envutil.set_value(iot_env, "SYSTEM1_ALERT_TOKEN", "")
    result = _run_in(
        iot_ai_project, ["ai", "system1", "enable", "--no-pull", "--source-ai", _AI_SOURCE]
    )
    assert result.exit_code == 0, result.output
    ai_env = envutil.load(iot_ai_project / "ai" / ".env")
    for key in ("SYSTEM1_API_KEY", "SYSTEM1_ALERT_TOKEN"):
        assert envutil.load(iot_env)[key] == ai_env[key]
    assert "copied to the iot layer" in result.output


def _kept(*rows):
    """Node-RED's kept feedback file, as `cat` prints it."""
    calls = []

    class Done:
        returncode, stderr = 0, ""
        stdout = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows) + "not json\n"

    def fake_compose(cwd, *args, **kw):
        calls.append((cwd, args))
        return Done()

    return calls, fake_compose


def _fb(id_, question, expected, text):
    return {
        "id": id_,
        "set": "operator-intake",
        "question": question,
        "expected": expected,
        "lang": "es",
        "state": {"text": text},
    }


def test_feedback_prints_and_appends_new_examples(iot_ai_project, monkeypatch):
    calls, fake = _kept(
        _fb("a", "intent", "report_fault", "La bomba 2 gotea."),
        _fb("a", "asset", "pump-2", "La bomba 2 gotea."),
        _fb("b", "asset", "pump", "La bomba."),  # a no-answer key: dropped
    )
    monkeypatch.setattr(ai, "_compose", fake)
    result = _run_in(iot_ai_project, ["ai", "system1", "feedback", "operator-intake"])
    assert result.exit_code == 0, result.output
    assert calls[0][0] == iot_ai_project / "iot"
    assert calls[0][1][-1] == "/data/system1/feedback/operator-intake.jsonl"
    [line] = [json.loads(x) for x in result.stdout.splitlines() if x.startswith("{")]
    assert line == {
        "state": {"text": "La bomba 2 gotea."},
        "expect": {"intent": "report_fault", "asset": "pump-2"},
        "source": "feedback",
        "id": "a",
        "lang": "es",
    }
    path = iot_ai_project / "ai" / SETS / "operator-intake.eval.jsonl"
    before = path.read_text()
    for _ in range(2):  # the second run finds nothing new
        result = _run_in(
            iot_ai_project, ["ai", "system1", "feedback", "operator-intake", "--append"]
        )
        assert result.exit_code == 0, result.output
    assert path.read_text() == before + json.dumps(line, ensure_ascii=False) + "\n"
    assert "Appended 0 examples" in result.output


def test_feedback_needs_an_iot_layer(ai_project, docker):
    result = _run_in(ai_project, ["ai", "system1", "feedback", "operator-intake"])
    assert result.exit_code == 1 and "no iot layer" in result.output


# ── calibration and labels ──────────────────────────────────────────────────


def test_save_calibration_writes_the_site_file(ai_project, docker, monkeypatch):
    _serving(docker[1])
    _fake_client(monkeypatch, lambda state: _cause("electrical", 0.99))
    result = _run_in(
        ai_project,
        ["ai", "system1", "eval", "--no-gates", "--fit-calibration", "--save-calibration"],
    )
    assert result.exit_code == 0, result.output
    site = json.loads((ai_project / ai.CALIBRATION_DIR / ai.CALIBRATION_FILE).read_text())
    assert set(site) >= {"choice:6-10"} and all(0.5 <= t <= 5 for t in site.values())
    assert envutil.load(ai_project / ".env")["SYSTEM1_CALIBRATION"] == "site.json"
    assert "bump every set's" in result.output


@pytest.mark.parametrize(
    "args", [["--save-calibration"], ["incident-triage", "--fit-calibration", "--save-calibration"]]
)
def test_save_calibration_needs_every_set(ai_project, docker, args):
    result = _run_in(ai_project, ["ai", "system1", "eval", *args])
    assert result.exit_code == 1 and "over every set" in result.output


def _events(tmp_path, rows):
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


EVENTS = [
    {"ts": "2026-09-01T08:00:00Z", "state": {"alert": "Smoke in cabinet 3"}, "subject": "cab-3"},
    {"ts": "2026-09-02T09:30:00Z", "state": {"alert": "Status changed."}, "subject": "gw-01"},
]


def test_label_prints_without_writing(ai_project, docker, monkeypatch, tmp_path):
    _serving(docker[1])
    _fake_client(
        monkeypatch,
        lambda st: _cause("electrical", 0.99) if "Smoke" in st["alert"] else _cause("thermal", 0.2),
    )
    result = _run_in(
        ai_project,
        ["ai", "system1", "label", "incident-triage", "--input", str(_events(tmp_path, EVENTS))],
    )
    assert result.exit_code == 0, result.output
    assert "electrical" in result.output and "(unlabelled)" in result.output
    assert "1 labels; write them with --write" in result.output
    assert docker[0] == []


def test_label_write_sends_line_protocol_to_influxdb(iot_ai_project, monkeypatch, tmp_path):
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(ai, "_compose", lambda cwd, *a, **kw: calls.append((cwd, a, kw)) or Done())
    monkeypatch.setattr(ai, "_container_state", lambda name: ("running", "healthy"))
    _fake_client(monkeypatch, lambda st: _cause("electrical", 0.99))
    events = _events(tmp_path, EVENTS)
    result = _run_in(
        iot_ai_project,
        ["ai", "system1", "label", "incident-triage", "--input", str(events), "--write"],
    )
    assert result.exit_code == 0, result.output
    [(cwd, args, kw)] = calls
    assert cwd == iot_ai_project / "iot"
    assert args[:4] == ("exec", "-T", "influxdb", "sh") and args[-1] == "ai_events"
    token = envutil.load(iot_ai_project / "iot" / ".env")["INFLUXDB_TOKEN"]
    assert token not in " ".join(args)
    lines = kw["input"].strip().splitlines()
    assert len(lines) == 2 and lines[0].startswith(
        "system1_label,caller=cli-label,choice=electrical"
    )
    assert "Wrote 2 labels to ai_events" in result.output


def test_label_rejects_bad_input(ai_project, docker, tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"state": {"alert": "x"}}\n')
    result = _run_in(ai_project, ["ai", "system1", "label", "incident-triage", "--input", str(bad)])
    assert result.exit_code == 1 and "needs 'ts' and 'state'" in result.output
