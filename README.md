# p4n4-cli

> Command-line tool for bootstrapping and managing **P4N4** projects — Platform for Nexus Neural Network Nodes.

`p4n4` scaffolds, configures, and orchestrates the P4N4 stack: the **MING** IoT services, Edge Impulse inference, and the Gen AI layer. It wraps `docker compose` with project-aware defaults and a guided setup flow.

Part of the [p4n4](https://github.com/raisga/p4n4) platform — an EdgeAI + GenAI integration platform for IoT deployments.

---

## Table of Contents

- [Overview](#overview)
- [Repository Map](#repository-map)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Local Development](#local-development)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Commands](#commands)
  - [p4n4 init](#p4n4-init)
  - [p4n4 up](#p4n4-up)
  - [p4n4 down](#p4n4-down)
  - [p4n4 status](#p4n4-status)
  - [p4n4 logs](#p4n4-logs)
  - [p4n4 secret](#p4n4-secret)
  - [p4n4 validate](#p4n4-validate)
  - [p4n4 add](#p4n4-add)
  - [p4n4 remove](#p4n4-remove)
  - [p4n4 upgrade](#p4n4-upgrade)
  - [p4n4 ei](#p4n4-ei)
  - [p4n4 template](#p4n4-template)
- [Layers](#layers)
- [Configuration Reference](#configuration-reference)
- [Default Ports](#default-ports)
- [Source Repos](#source-repos)
- [Resources](#resources)
- [License](#license)

---

## Overview

P4N4 is a unified developer platform for IoT and Edge AI. It combines the **MING stack** (Mosquitto, InfluxDB, Node-RED, Grafana), **Edge Impulse** on-device ML inference, and a **Gen AI layer** (n8n, Letta, Ollama) into a single composable system.

`p4n4-cli` manages the full lifecycle — init, run, inspect, and tear down — from your terminal. Stack files are always fetched from the canonical source repos at init time, so projects are never pinned to a snapshot bundled inside the CLI.

---

## Repository Map

| Repository | Description |
|------------|-------------|
| **[p4n4](https://github.com/raisga/p4n4)** | Umbrella repo — architecture, ADRs, cross-cutting docs |
| [p4n4-iot](https://github.com/raisga/p4n4-iot) | IoT stack: Mosquitto · InfluxDB · Node-RED · Grafana |
| [p4n4-ai](https://github.com/raisga/p4n4-ai) | GenAI stack: Ollama · Letta · n8n |
| [p4n4-edge](https://github.com/raisga/p4n4-edge) | Edge Impulse inference stack |
| [p4n4-api](https://github.com/raisga/p4n4-api) | Rust REST API gateway (port 8000) |
| [p4n4-lib](https://github.com/raisga/p4n4-lib) | Shared Rust library (`pip install p4n4lib` for Python bindings) |
| **[p4n4-cli](https://github.com/raisga/p4n4-cli)** | This repo — Python CLI (`pip install p4n4`) |
| [p4n4-templates](https://github.com/raisga/p4n4-templates) | Community template registry |
| [p4n4-docs](https://github.com/raisga/p4n4-docs) | Full technical documentation site |

---

## Prerequisites

- **Python** 3.11+
- **Git** (required by `p4n4 init` to clone stack repos)
- **Docker** v24+ (with Compose v2)
- **pipx** (recommended for isolated installation)
- At least **4 GB RAM** available to Docker (8 GB recommended when running Ollama)

Install `pipx` if you don't have it:

```bash
# macOS
brew install pipx && pipx ensurepath

# Linux / WSL
python3 -m pip install --user pipx && python3 -m pipx ensurepath
```

---

## Installation

```bash
pipx install p4n4
```

Or with plain pip:

```bash
pip install p4n4
```

Verify:

```bash
p4n4 --version
```

Upgrade / uninstall:

```bash
pipx upgrade p4n4
pipx uninstall p4n4
```

---

## Local Development

```bash
# 1. Clone the repo
git clone https://github.com/raisga/p4n4-cli.git
cd p4n4-cli

# 2. Create the virtual environment
uv venv
source .venv/bin/activate

# 3. Install in editable mode with dev extras
uv pip install -e ".[dev]"

# 4. Verify
p4n4 --help

# 5. Run tests
pytest tests/ -v

# 6. Lint
ruff check .
```

---

## Quick Start

```bash
# Scaffold a new IoT project (fetches latest files from p4n4-iot)
p4n4 init my-project
cd my-project

# Validate the generated config
p4n4 validate

# Start the MING stack
p4n4 up

# Check service health
p4n4 status

# Tail logs from a specific service
p4n4 logs grafana

# Stop the stack
p4n4 down
```

**Scaffold a GenAI project instead:**

```bash
p4n4 init my-ai-project --layer ai
cd my-ai-project
p4n4 up
```

**Scaffold with all layers:**

```bash
p4n4 init my-full-project --layer all
cd my-full-project
p4n4 up
p4n4 up --ai
```

**No internet access?** Point `--source-iot` / `--source-ai` at local checkouts:

```bash
p4n4 init my-project --source-iot ../p4n4-iot
p4n4 init my-ai-project --layer ai --source-ai ../p4n4-ai
```

Once the IoT stack is up:

| Service  | URL                   |
|----------|-----------------------|
| Grafana  | http://localhost:3000 |
| Node-RED | http://localhost:1880 |
| InfluxDB | http://localhost:8086 |

Once the AI stack is up:

| Service | URL                    |
|---------|------------------------|
| n8n     | http://localhost:5678  |
| Letta   | http://localhost:8283  |
| Ollama  | http://localhost:11434 |

---

## Project Structure

After `p4n4 init`, the project directory contains files sourced from the relevant stack repo(s). Stack files are never modified by the CLI after scaffolding.

**IoT layer (`--layer iot`, the default):**

```
my-project/
├── .p4n4.json                       # Manifest (project name, active layers, schema version)
├── .env                             # Credentials and config (auto-generated secrets)
├── docker-compose.yml               # Stack orchestration (sourced from p4n4-iot)
├── config/
│   ├── mosquitto/
│   │   ├── mosquitto.conf           # MQTT broker config
│   │   ├── passwd.example           # Auth template for production hardening
│   │   └── acl.example              # ACL template
│   ├── node-red/
│   │   ├── settings.js              # Node-RED runtime settings
│   │   └── flows.json               # MQTT → InfluxDB pipeline
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── datasources.yml  # Pre-configured InfluxDB datasources (5 buckets)
│           └── dashboards/
│               ├── dashboards.yml
│               └── json/
│                   └── iot-overview.json
└── scripts/
    ├── init-buckets.sh              # Creates additional InfluxDB buckets on first run
    ├── init-sandbox.sh
    └── selector.sh
```

**AI layer (`--layer ai`):**

```
my-ai-project/
├── .p4n4.json                       # Manifest
├── .env                             # Credentials and config (auto-generated secrets)
├── docker-compose.yml               # Stack orchestration (sourced from p4n4-ai)
├── config/
│   ├── letta/
│   │   └── letta.conf               # Letta agent server config
│   ├── n8n/
│   │   └── workflows/               # Pre-built n8n workflow definitions
│   │       ├── alert-enrichment.json
│   │       ├── device-onboarding.json
│   │       ├── incident-escalation.json
│   │       └── scheduled-digest.json
│   └── ollama/                      # Ollama model storage (populated at runtime)
└── scripts/
    ├── pull-models.sh               # Pull default Ollama models
    └── selector.sh
```

---

## Commands

### `p4n4 init`

Scaffold a new P4N4 project. Clones the canonical stack repo(s) at init time so the project always starts from the latest source.

```bash
p4n4 init <project-name> [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--layer <name>` | Layers to enable: `iot`, `ai`, `edge`, `all`, or comma-separated | `iot` |
| `--no-interactive` | Skip the wizard and use generated defaults | — |
| `--source-iot <path>` | Local p4n4-iot checkout (skips git clone; useful offline) | — |
| `--source-ai <path>` | Local p4n4-ai checkout (skips git clone; useful offline) | — |

The interactive wizard prompts for InfluxDB org, timezone, and admin passwords. When the `ai` layer is active it also prompts for Letta, n8n, and n8n encryption key values. All secrets default to randomly generated values if left blank.

```bash
# IoT stack, interactive wizard (default)
p4n4 init sensor-network

# GenAI stack, non-interactive
p4n4 init my-ai-project --layer ai --no-interactive

# All layers enabled
p4n4 init my-full-project --layer all

# From local checkouts (no network required)
p4n4 init sensor-network --source-iot ../p4n4-iot --no-interactive
p4n4 init my-ai-project --layer ai --source-ai ../p4n4-ai --no-interactive
```

---

### `p4n4 up`

Start the project stack (`docker compose up -d`).

```bash
p4n4 up [options]
```

| Flag | Description |
|------|-------------|
| `--ai` | Start Gen AI services only |
| `--edge` | Start Edge AI services only |
| `--build` | Rebuild images before starting |
| `--pull` | Pull the latest images before starting |

```bash
p4n4 up
p4n4 up --pull
p4n4 up --ai
p4n4 up --edge
```

---

### `p4n4 down`

Stop all running services.

```bash
p4n4 down [options]
```

| Flag | Description |
|------|-------------|
| `--volumes` | Also remove persistent data volumes _(destructive — prompts for confirmation)_ |

```bash
p4n4 down

# Full teardown — deletes all stored data
p4n4 down --volumes
```

---

### `p4n4 status`

Print a service status table.

```bash
p4n4 status
```

```
       Stack status — my-project
┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Service   ┃ Status  ┃ Health  ┃ Ports                 ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ mqtt      │ running │ healthy │ 1883→1883/tcp          │
│ influxdb  │ running │ healthy │ 8086→8086/tcp          │
│ node-red  │ running │ healthy │ 1880→1880/tcp          │
│ grafana   │ running │ healthy │ 3000→3000/tcp          │
└───────────┴─────────┴─────────┴───────────────────────┘
```

---

### `p4n4 logs`

Stream logs from all services or a specific one.

```bash
p4n4 logs [service] [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--tail <n>` | Lines from end of existing logs | `100` |
| `--no-follow` | Print once and exit | — |

```bash
p4n4 logs
p4n4 logs node-red
p4n4 logs influxdb --tail 50 --no-follow
```

---

### `p4n4 secret`

Rotate secrets in `.env` with new randomly generated values. Prompts for confirmation before writing. Rotates whichever of the following keys are present:

- **IoT layer:** `INFLUXDB_PASSWORD`, `INFLUXDB_TOKEN`, `GRAFANA_PASSWORD`
- **AI layer:** `LETTA_SERVER_PASSWORD`, `N8N_BASIC_AUTH_PASSWORD`, `N8N_ENCRYPTION_KEY`

```bash
p4n4 secret
```

Run `p4n4 down && p4n4 up` after rotating secrets to apply them.

---

### `p4n4 validate`

Check that `.p4n4.json`, `.env`, and all required config files are present and valid for the active layers.

```bash
p4n4 validate
```

---

### `p4n4 add`

Add a layer or service to an existing project.

```bash
p4n4 add <component>
```

> Not yet implemented.

---

### `p4n4 remove`

Remove a layer or service from an existing project.

```bash
p4n4 remove <component>
```

> Not yet implemented.

---

### `p4n4 upgrade`

Pull the latest Docker images for all active services.

```bash
p4n4 upgrade
```

> Not yet implemented.

---

### `p4n4 ei`

Manage Edge Impulse model deployment and inference.

```bash
p4n4 ei deploy
p4n4 ei run
```

| Subcommand | Description |
|------------|-------------|
| `deploy` | Deploy a trained Edge Impulse model to the edge device |
| `run` | Run inference and publish results over MQTT |

> Not yet implemented.

---

### `p4n4 template`

Browse and apply community project templates.

```bash
p4n4 template search [query]
p4n4 template apply <name>
```

> Not yet implemented.

---

## Layers

P4N4 is organized into three composable layers.

### IoT — MING Stack

| Service | Role |
|---------|------|
| **Mosquitto** | MQTT broker — central message bus |
| **InfluxDB** | Time-series database (5 pre-configured buckets) |
| **Node-RED** | Flow engine for MQTT routing and pipeline logic |
| **Grafana** | Real-time dashboarding and alerting |

### Edge

| Service | Role |
|---------|------|
| **Edge Impulse** | On-device ML inference; publishes results over MQTT |

### Gen AI

| Service | Role |
|---------|------|
| **n8n** | Workflow automation bridging IoT and AI layers |
| **Letta** | Stateful AI agent framework with long-term memory |
| **Ollama** | Local LLM runtime for open-weight models |

All three stacks communicate over a shared `p4n4-net` Docker bridge network owned by `p4n4-iot`. The CLI handles network creation and stack ordering automatically.

---

## Configuration Reference

`.env` is generated by `p4n4 init` with random secrets. Use `p4n4 secret` to rotate credentials at any time.

**IoT layer:**

```bash
TZ=UTC

# InfluxDB
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=<generated>
INFLUXDB_ORG=ming
INFLUXDB_TOKEN=<generated>
INFLUXDB_BUCKET=raw_telemetry
INFLUXDB_BUCKET_PROCESSED=processed_metrics
INFLUXDB_BUCKET_AI_EVENTS=ai_events
INFLUXDB_BUCKET_HEALTH=system_health
INFLUXDB_SANDBOX_BUCKET=sandbox
INFLUXDB_SANDBOX_RETENTION=30d

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=<generated>
```

**AI layer:**

```bash
# Letta
LETTA_SERVER_PASSWORD=<generated>

# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<generated>
N8N_ENCRYPTION_KEY=<generated>   # 32+ characters
N8N_HOST=localhost

# Shared InfluxDB (must match p4n4-iot values when used alongside it)
INFLUXDB_TOKEN=<generated>
INFLUXDB_ORG=ming
INFLUXDB_BUCKET=raw_telemetry
```

---

## Default Ports

| Service              | Port                              | Stack |
|----------------------|-----------------------------------|-------|
| MQTT (Mosquitto)     | `1883` (MQTT), `9001` (WebSocket) | iot   |
| InfluxDB             | `8086`                            | iot   |
| Node-RED             | `1880`                            | iot   |
| Grafana              | `3000`                            | iot   |
| n8n                  | `5678`                            | ai    |
| Letta                | `8283`                            | ai    |
| Ollama               | `11434`                           | ai    |
| Edge Impulse Runner  | `8080` (health endpoint)          | edge  |
| **p4n4 REST API**    | **`8000`**                        | **api** |

---

## Source Repos

Stack files are fetched from these repos at `p4n4 init` time. URLs are defined in [`p4n4/sources.yaml`](p4n4/sources.yaml) and can be overridden per-layer via `--source-iot` / `--source-ai`, or by editing the file to point at a fork or mirror.

| Layer     | Repo |
|-----------|------|
| IoT       | https://github.com/raisga/p4n4-iot |
| AI        | https://github.com/raisga/p4n4-ai |
| Edge      | https://github.com/raisga/p4n4-edge |
| Templates | https://github.com/raisga/p4n4-templates |

---

## Resources

- [p4n4.com](https://p4n4.com) — Platform overview
- [Full documentation](https://raisga.github.io/p4n4-docs) — MkDocs reference site
- [p4n4-iot](https://github.com/raisga/p4n4-iot) — MING stack source
- [p4n4-ai](https://github.com/raisga/p4n4-ai) — GenAI stack source
- [p4n4-edge](https://github.com/raisga/p4n4-edge) — Edge AI stack source
- [p4n4-templates](https://github.com/raisga/p4n4-templates) — Community template registry
- [MING Stack Tutorial](https://github.com/ArthurKretzer/tutorial-p4n4-stack) — IIoT data stack tutorial (XIV SBESC, 2024)
- [MING Stack with Edge Impulse](https://www.edgeimpulse.com/blog/accelerate-edge-ai-application-development-with-the-p4n4-stack-edge-impulse/) — Integration guide
- [Edge Impulse Linux SDK (Python)](https://github.com/edgeimpulse/linux-sdk-python)
- [Eclipse Mosquitto](https://mosquitto.org/) · [InfluxDB](https://docs.influxdata.com/) · [Node-RED](https://nodered.org/docs/) · [Grafana](https://grafana.com/docs/)
- [Ollama](https://github.com/ollama/ollama) · [Letta](https://docs.letta.com/) · [n8n](https://docs.n8n.io/)

---

## License

This project is licensed under the [MIT License](LICENSE).
