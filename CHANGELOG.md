# Changelog

All notable changes to `p4n4` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- `p4n4 down --all`: stops every p4n4 project on the host, from any directory. It lists
  each project with its folder and containers and asks first; `--volumes` also deletes
  their data. Projects that own `p4n4-net` stop last, so the network is removed too.

### Changed

- `p4n4 up` checks every stack before starting any of them. If another project's
  containers hold the fixed `p4n4-*` names (another p4n4 project is still up), it lists
  them and prints the command that stops each owner, instead of starting part of the
  project and then failing with Docker's "container name is already in use" error.
  The error also suggests `p4n4 down --all`.
- `p4n4 secret rotate` no longer rotates `INFLUXDB_PASSWORD`, `INFLUXDB_TOKEN`,
  `GRAFANA_PASSWORD`, `N8N_ENCRYPTION_KEY` or the unused `N8N_BASIC_AUTH_PASSWORD`, and
  says so. Their services keep the value from first setup, so rotating `.env` alone
  locked every client out of InfluxDB and Grafana, and stopped n8n from starting.
  `SECURITY.md` explains how to change them inside the services. `secret show` still
  lists them.
- `p4n4 init` writes `TZ` to the AI layer's `.env` too, so n8n's schedules and date
  expressions use the project's timezone instead of America/New_York.

### Fixed

- AI-only and edge-only projects start: `p4n4 up` creates the `p4n4-net` network those
  stacks join when it's missing. Only the IoT stack created it, so `up` failed without
  it. The same goes for `p4n4 up ai` while the IoT stack is down.
- `p4n4 status` lists stopped and crashed services, and reports an error when Docker or
  Compose fails, instead of "No services found".
- Ctrl+C at a `p4n4 init` prompt aborts. Before, it took the prompt's default and
  carried on scaffolding.
- `p4n4 init` checks that a typed n8n encryption key has the 32 characters it asks for.

`secret rotate`, `up` and `status` need `p4n4-lib` with `secrets.SETUP_KEYS`,
`compose.ensure_network` and the new `compose.ps` (unreleased). Both `up` changes
need `p4n4-lib` with `compose.name_conflicts`, `host_projects` and `down_project`
(unreleased).

## [0.2.0] - 2026-10-03

### Upgrading from 0.1.x

- Multi-layer projects now keep each layer in its own subdirectory (`iot/`, `ai/`, …).
  Projects created by 0.1.x with more than one layer use the old flat layout: create a
  new project with `p4n4 init` and copy your data and `.env` values across.
- The IoT `.env` needs `NODE_RED_USER` and `NODE_RED_PASSWORD` (see Security below).
- New projects set `COMPOSE_PROJECT_NAME` in each layer's `.env` (see Fixed below). Existing
  projects keep their old names: **don't add it to an existing project** unless you also move its
  volumes, because Compose would start on new, empty ones.
- The stacks now put every service in a Compose profile, and `COMPOSE_PROFILES` in each
  layer's `.env` picks the ones that start. New projects get each stack's default: the MING
  services, Ollama only for the AI layer, and the inference runner for edge.
- p4n4 0.2.x is meant for trusted networks only. Don't expose its service ports to the
  internet or to networks you don't control.

### Added

- `dashboard` layer: `p4n4 init --layer dashboard` (or `iot,dashboard`) scaffolds the
  p4n4-dashboard web service: its `docker-compose.yml` (the released image on port 8088,
  proxying p4n4-api, Ollama and Letta) and a `.env` from the repo's `.env.example`.
  `--source-dashboard` scaffolds from a local checkout. `p4n4 up` starts it after the
  other stacks and prints its URL, and `p4n4 down` stops it first.
  With the dashboard enabled, the IoT `.env` gets `GRAFANA_ALLOW_EMBEDDING=true` so its
  web UI can frame Grafana (`false` otherwise).
- External MQTT broker: `p4n4 init` (wizard, or `--mqtt-remote HOST[:PORT]` with
  `--mqtt-remote-user`, `--mqtt-remote-password` / `P4N4_MQTT_REMOTE_PASSWORD`,
  `--mqtt-remote-topics`, `--mqtt-remote-tls`, `--mqtt-remote-ca`) configures the IoT
  stack's Mosquitto bridge, which pulls topics from another broker into the local one.
  `p4n4 secret show` lists `MQTT_REMOTE_PASSWORD` fully masked; `rotate` leaves it alone.
- `--source-edge` flag on `p4n4 init` for offline scaffolding of the edge stack
- `p4n4 up <stack>` / `p4n4 down <stack>` now actually filter to one stack; with no
  argument they run all enabled stacks in dependency order (iot → ai → edge, reversed
  for `down`)
- `p4n4 logs --stack <name>` to pick a stack in multi-layer projects (required when
  following logs; `--no-follow` dumps all stacks)
- `p4n4 status` prints one table per stack in multi-layer projects
- `p4n4 secret show` gains a Stack column in multi-layer projects; `p4n4 secret rotate`
  rotates across all layer `.env` files, keeping shared keys (e.g. `INFLUXDB_TOKEN`)
  identical in every file
- `p4n4 validate` checks each layer's files and `.env` in its own directory, with
  `iot/`-style prefixes in multi-layer output
- `p4n4 validate` checks the `.p4n4.json` `dashboard` block (`grafana_path`, `tabs`,
  `theme`) and that a named theme directory has a `brand.json`.

### Changed

- Shared, framework-agnostic code extracted into the new [`p4n4-lib`](https://github.com/raisga/p4n4-lib)
  package, now a dependency (`p4n4-lib>=0.2.0`): manifest, dotenv, Docker Compose
  wrappers, layer registry (repo URLs, copy paths, required files/env keys), scaffolding,
  validation, and secret generation all live in `p4n4_lib`
- `p4n4/utils/`, `p4n4/sources.py`, and `p4n4/sources.yaml` removed in favour of `p4n4_lib`
- Duplicate token generators in `init`/`secret` unified as `p4n4_lib.secrets`
- "No .p4n4.json found" error message unified across commands via `p4n4.project.require_manifest`
- `p4n4 init --layer all` enables every registered layer, which now includes `edge` and
  `dashboard`.
- The AI layer starts only Ollama by default. Letta and n8n are optional: `init` still
  generates their secrets and prints how to enable them (`COMPOSE_PROFILES=ollama,letta,n8n`
  in the AI `.env`). The wizard's Letta and n8n prompts say they're optional.
- Projects created from a template (`.p4n4.json` has a `template` block) are validated
  against the template's own `.env.example` instead of the base stack's file list, so a
  `mqtt-influx-grafana` project no longer fails on missing Node-RED files.
- `p4n4 down` stops every service in the stack, including ones outside `COMPOSE_PROFILES`
  (via `p4n4-lib`).
- Typer is pinned to a tested range (`>=0.12,<0.28`).
- Tests locate local stack checkouts via sibling repos (CI) or `stacks/<name>` (monorepo),
  and no longer use `CliRunner.isolated_filesystem`, which Typer 0.27 removed.

### Fixed

- `p4n4 init --layer iot,ai` (and `--layer all`) no longer crashes on file collisions:
  multi-layer projects now scaffold each layer into its own subdirectory
  (`<project>/iot/`, `<project>/ai/`) with its own compose file, config, and `.env`,
  matching how the stacks are designed to run (separate Compose projects sharing the
  `p4n4-net` network). Single-layer projects keep the flat layout.
- `p4n4 init --layer all` and `--layer edge` now scaffold the edge stack (compose file,
  runner, model directories and `.env`, sharing the InfluxDB token, org and timezone with
  the other layers). Previously edge was recorded in `.p4n4.json` without any files, and
  `p4n4 validate` passed because the edge layer defined nothing to check.
- `p4n4 init` rejects unknown layer names instead of recording them in `.p4n4.json`.
- Two multi-layer projects on one host no longer share volumes. Compose named each layer after
  its directory (`iot`, `ai`, …), so a second project silently reused the first one's data, and
  InfluxDB skipped its first-run setup. `init` now writes `COMPOSE_PROJECT_NAME`: `<project>` for
  single-layer projects, `<project>-<layer>` for multi-layer ones.
- Lifecycle commands show a clean error instead of a traceback when Docker Compose is
  missing; the standalone `docker-compose` (v1) is used when the v2 plugin is absent.
- `.env` values containing `$`, `#`, spaces or quotes are quoted so Docker Compose reads
  them literally (via `p4n4-lib`); before, a `$` was interpolated and ` #` cut the value.
- Windows: scaffolded shell scripts keep LF line endings (stacks are cloned with
  `core.autocrlf=false`), `.env` and `.p4n4.json` are written as UTF-8 with LF endings,
  and commands no longer fail with `UnicodeEncodeError` when their output is redirected.

### Security

- The Node-RED editor and Admin API now require a login. `p4n4 init` generates
  `NODE_RED_PASSWORD` (or prompts for it after the Grafana password) and writes it with
  `NODE_RED_USER=admin` to the IoT `.env`. `p4n4 validate` requires both keys, and
  `p4n4 secret rotate` rotates the password. Existing projects must add both keys to their
  IoT `.env`; until then the editor refuses every login.

---

## [0.1.1] - 2026-05-14

### Fixed

- Project version number alignment between `pyproject.toml` and `p4n4/__init__.py`

### Changed

- `p4n4 secret` is now a sub-app with three subcommands: `show`, `rotate`, `generate`
- `p4n4 template apply` renamed to `p4n4 template install` to match CLI reference
- `p4n4 up` signature: replaced `--edge`/`--ai` flags with an optional `STACK` positional
  argument; added `--no-detach` for foreground mode
- `p4n4 down` signature: added optional `STACK` positional argument
- `p4n4 ei deploy` now requires a `MODEL_FILE` positional argument
- `compose.up()` accepts a `detach` parameter (default `True`)

### Added

- `p4n4 secret show` - display masked secrets from `.env`
- `p4n4 secret generate` - print new secret values to stdout without writing to disk
- `p4n4 template list` - show installed templates
- `p4n4 ei status` - show runner container status

### Removed

- `p4n4 up --edge` and `p4n4 up --ai` flags (superseded by the `STACK` argument)

---

## [0.1.0] - 2026-05-01

### Added

- `p4n4 init` - interactive wizard; scaffolds IoT and AI layers from canonical repos
- `p4n4 up / down / status / logs` - Docker Compose lifecycle management
- `p4n4 validate` - checks manifest, required files, and `.env` keys
- `p4n4 secret` - secret rotation for IoT and AI layer credentials
- `p4n4 add / remove` - stub commands for layer management
- `p4n4 upgrade` - stub command for image upgrades
- `p4n4 ei` sub-app - stub commands for Edge Impulse model lifecycle
- `p4n4 template` sub-app - stub commands for community template registry
- `--source-iot` / `--source-ai` flags on `p4n4 init` for offline scaffolding
- CI matrix across Python 3.11, 3.12, 3.13
- PyPI publishing workflow via Trusted Publisher

[Unreleased]: https://github.com/raisga/p4n4-cli/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/raisga/p4n4-cli/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/raisga/p4n4-cli/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raisga/p4n4-cli/releases/tag/v0.1.0
