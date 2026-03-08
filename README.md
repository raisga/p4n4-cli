# p4n4-cli

> Command-line tool for bootstrapping and managing **P4N4** projects — Platform for Nexus Neural Network Nodes.

`p4n4` is a developer-facing CLI that scaffolds, configures, and orchestrates the full P4N4 stack: MING services, Edge Impulse inference, and the Gen AI layer. It wraps `docker compose` with project-aware defaults and a guided setup flow, so engineers can go from zero to a running edge AI system in minutes.

---

## Table of Contents

- [Overview](#overview)
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
  - [p4n4 service](#p4n4-service)
  - [p4n4 model](#p4n4-model)
  - [p4n4 config](#p4n4-config)
- [Layers](#layers)
- [Configuration Reference](#configuration-reference)
- [Default Ports](#default-ports)
- [Default Credentials](#default-credentials)
- [Resources](#resources)
- [License](#license)

---

## Overview

P4N4 is a unified developer platform for IoT and Edge AI engineers. It combines the **MING stack** (MQTT, InfluxDB, Node-RED, Grafana), **Edge Impulse** on-device ML inference, and a **Gen AI layer** (n8n, Letta, Ollama, Kokoro) into a single, composable system.

```
    ┌───────────────────────────────────────────────────────────────────────┐
    │                              Edge AI Layer                            │
    └───────────────────────────────────────────────────────────────────────┘
     [Edge Impulse] ──► [MQTT] ──► [Node-RED]  ──► [InfluxDB]  ──► [Grafana]
                           │           ▲               ▲
                           │           │               │
                           ▼           │               │
                         ┌───────────────────────────────┐
  [Loc/Cld Services] ─── │          Gen AI Layer         │
                         └───────────────────────────────┘
                                  [n8n]
                                 /     \
                                ▼       ▼
                           [Letta]   [Kokoro]
                              │
                              ▼
                          [Ollama]
```

`p4n4-cli` manages the entire lifecycle of a P4N4 project from your terminal.

---

## Prerequisites

- **Python** 3.11+
- **pipx** (for isolated installation)
- **Docker** v20.10+
- **Docker Compose** v2.0+
- At least **8 GB RAM** available to Docker (16 GB recommended when running Ollama with larger models)
- An [Edge Impulse](https://edgeimpulse.com/) account and a trained project _(optional, for on-device inference)_

Install `pipx` if you don't have it:

```bash
# macOS
brew install pipx
pipx ensurepath

# Linux / WSL
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

---

## Installation

```bash
pipx install p4n4
```

Verify the installation:

```bash
p4n4 --version
```

To upgrade to the latest release:

```bash
pipx upgrade p4n4
```

To uninstall:

```bash
pipx uninstall p4n4
```

---

## Local Development

### 1. Clone and navigate to the repo

```bash
git clone https://github.com/raisga/p4n4-cli.git
cd p4n4-cli
```

### 2. Create and activate the virtual environment

```bash
uv venv                        # creates .venv/ (skip if already exists)
source .venv/bin/activate
```

### 3. Install in editable mode

```bash
uv pip install -e ".[dev]"
```

The `[dev]` extra pulls in `pytest` and `ruff`. Omit it if you only need the CLI.

### 4. Run the CLI

```bash
p4n4 --help
p4n4 --version
```

Or without activating the venv:

```bash
.venv/bin/p4n4 --help
```

### 5. Run the tests

```bash
pytest tests/ -v
```

### 6. Run the linter

```bash
ruff check .
```

---

## Quick Start

```bash
# 1. Create a new project
p4n4 init my-edge-project
cd my-edge-project

# 2. Start the full stack
p4n4 up

# 3. Check that all services are running
p4n4 status

# 4. Pull a local LLM (optional)
p4n4 model pull llama3.2

# 5. Stop everything when done
p4n4 down
```

Once the stack is up, open the service dashboards:

| Service  | URL                      |
|----------|--------------------------|
| Grafana  | http://localhost:3000    |
| Node-RED | http://localhost:1880    |
| n8n      | http://localhost:5678    |
| InfluxDB | http://localhost:8086    |
| Letta    | http://localhost:8283    |
| Ollama   | http://localhost:11434   |
| Kokoro   | http://localhost:8880    |

---

## Project Structure

After running `p4n4 init`, your project directory will look like this:

```
my-edge-project/
├── p4n4.yml                    # Project manifest (name, enabled layers, settings)
├── .env                        # Environment variables (credentials, model names)
├── docker-compose.yml          # Generated orchestration file
├── config/
│   ├── mosquitto/
│   │   └── mosquitto.conf      # MQTT broker configuration
│   ├── node-red/
│   │   ├── settings.js         # Node-RED runtime settings
│   │   └── flows.json          # Starter MQTT-to-InfluxDB flow
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── datasources.yml   # Auto-configured InfluxDB datasource
│           └── dashboards/
│               ├── dashboards.yml
│               └── json/
│                   └── iot-overview.json  # Starter IoT dashboard
├── scripts/
│   └── inference.py            # Edge Impulse inference + MQTT publisher
└── README.md                   # Project-level notes
```

`p4n4.yml` is the single source of truth for what layers and services are active. Edit it to enable or disable components before running `p4n4 up`.

---

## Commands

### `p4n4 init`

Scaffold a new P4N4 project with an interactive setup wizard.

```bash
p4n4 init <project-name> [options]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--layer edge` | Enable only the Edge AI layer (MING + Edge Impulse) | — |
| `--layer genai` | Enable only the Gen AI layer (n8n, Ollama, Letta, Kokoro) | — |
| `--layer all` | Enable all layers | `all` |
| `--model <name>` | Default Ollama model to pre-configure | `llama3.2` |
| `--no-interactive` | Skip the wizard and use defaults | — |

**Example:**

```bash
# Full stack with interactive wizard
p4n4 init warehouse-safety

# Edge AI layer only, no prompts
p4n4 init sensor-network --layer edge --no-interactive
```

---

### `p4n4 up`

Start the project stack. Equivalent to `docker compose up -d` with project-aware configuration.

```bash
p4n4 up [options]
```

**Options:**

| Flag | Description |
|------|-------------|
| `--edge` | Start only Edge AI services (MQTT, InfluxDB, Node-RED, Grafana) |
| `--genai` | Start only Gen AI services (n8n, Ollama, Letta, Kokoro) |
| `--build` | Rebuild images before starting |
| `--pull` | Pull the latest images before starting |

**Example:**

```bash
# Start everything
p4n4 up

# Start just the MING stack for data pipeline work
p4n4 up --edge
```

---

### `p4n4 down`

Stop all running services for the current project.

```bash
p4n4 down [options]
```

**Options:**

| Flag | Description |
|------|-------------|
| `--volumes` | Also remove persistent data volumes _(destructive)_ |

**Example:**

```bash
p4n4 down

# Full teardown — removes all stored data
p4n4 down --volumes
```

---

### `p4n4 status`

Print a service status table showing which containers are running, their ports, and their layer.

```bash
p4n4 status
```

**Example output:**

```
  P4N4 :: my-edge-project — Service Status
  ══════════════════════════════════════════════════════════════════
  SERVICE        STATUS       PORT     LAYER        URL
  ─────────────  ──────────   ──────   ──────────   ─────────────────────────
  mqtt           running      1883     Edge AI      -
  influxdb       running      8086     Edge AI      http://localhost:8086
  node-red       running      1880     Edge AI      http://localhost:1880
  grafana        running      3000     Edge AI      http://localhost:3000
  n8n            running      5678     Gen AI       http://localhost:5678
  ollama         running      11434    Gen AI       http://localhost:11434
  letta          running      8283     Gen AI       http://localhost:8283
  kokoro         stopped      8880     Gen AI       -
```

---

### `p4n4 logs`

Stream logs from all services (or a specific one).

```bash
p4n4 logs [service] [options]
```

**Options:**

| Flag | Description |
|------|-------------|
| `--tail <n>` | Number of lines to show from the end of existing logs |
| `--no-follow` | Print logs once and exit |

**Example:**

```bash
# Follow all logs
p4n4 logs

# Follow Node-RED logs only
p4n4 logs node-red

# Last 50 lines from InfluxDB, then exit
p4n4 logs influxdb --tail 50 --no-follow
```

---

### `p4n4 service`

Start or stop individual services with automatic dependency resolution.

```bash
p4n4 service start <name>
p4n4 service stop <name>
p4n4 service restart <name>
```

The CLI is aware of service dependencies. Starting `node-red` will automatically bring up `mqtt` and `influxdb` if they are not already running. Stopping `mqtt` will warn you if `node-red` or `n8n` depend on it.

**Available services:** `mqtt`, `influxdb`, `node-red`, `grafana`, `n8n`, `ollama`, `letta`, `kokoro`

**Example:**

```bash
# Start Node-RED (auto-starts mqtt and influxdb)
p4n4 service start node-red

# Stop Ollama (warns about Letta dependency if running)
p4n4 service stop ollama

# Restart Grafana
p4n4 service restart grafana
```

---

### `p4n4 model`

Manage Ollama models used by the Gen AI layer.

```bash
p4n4 model pull <name>
p4n4 model list
p4n4 model remove <name>
```

**Example:**

```bash
# Pull the default LLM
p4n4 model pull llama3.2

# Pull a smaller model for resource-constrained environments
p4n4 model pull gemma:2b

# List downloaded models
p4n4 model list

# Remove a model
p4n4 model remove llama3.2
```

---

### `p4n4 config`

View or edit the active project configuration.

```bash
p4n4 config show
p4n4 config set <key> <value>
p4n4 config get <key>
```

**Example:**

```bash
# Show all current configuration
p4n4 config show

# Change the Grafana admin password
p4n4 config set grafana.password my-secure-password

# Check a single key
p4n4 config get influxdb.token
```

Changes to credentials in `.env` take effect on the next `p4n4 up` or `p4n4 service restart <name>`.

---

## Layers

P4N4 is organized into two composable layers. You can run either independently or together.

### Edge AI Layer

| Service | Role |
|---------|------|
| **Eclipse Mosquitto (MQTT)** | Lightweight message broker — central nervous system of the IoT pipeline |
| **InfluxDB** | Time-series database for sensor readings and inference results |
| **Node-RED** | Low-code flow engine for MQTT routing, business logic, and orchestration |
| **Grafana** | Real-time dashboarding and alerting over InfluxDB data |
| **Edge Impulse** | On-device ML inference; publishes classification results over MQTT |

### Gen AI Layer

| Service | Role |
|---------|------|
| **n8n** | Workflow automation — bridges the Edge AI and Gen AI layers via MQTT/InfluxDB triggers |
| **Letta** | Stateful AI agent framework with long-term memory backed by Ollama |
| **Ollama** | Local LLM runtime — runs open-weight models entirely on local hardware |
| **Kokoro** | Fast local text-to-speech for voice alerts and spoken summaries |

---

## Configuration Reference

All configuration lives in `.env` at the project root. `p4n4 init` generates this file from a template. Key variables:

```bash
# ── Project ────────────────────────────────────────────────────────────────
P4N4_PROJECT_NAME=my-edge-project

# ── InfluxDB ───────────────────────────────────────────────────────────────
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=adminpassword
INFLUXDB_ORG=p4n4
INFLUXDB_BUCKET=iot-data
INFLUXDB_TOKEN=your-influxdb-token

# ── Grafana ────────────────────────────────────────────────────────────────
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=adminpassword

# ── n8n ────────────────────────────────────────────────────────────────────
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=adminpassword

# ── Ollama ─────────────────────────────────────────────────────────────────
OLLAMA_DEFAULT_MODEL=llama3.2

# ── Edge Impulse ───────────────────────────────────────────────────────────
EI_MODEL_PATH=/app/model/model.eim
MQTT_TOPIC_INFERENCE=inference/results
```

> **Note:** Change all passwords before deploying to any networked or production environment.

---

## Default Ports

| Service          | Port                              |
|------------------|-----------------------------------|
| MQTT (Mosquitto) | `1883` (MQTT), `9001` (WebSocket) |
| InfluxDB         | `8086`                            |
| Node-RED         | `1880`                            |
| Grafana          | `3000`                            |
| n8n              | `5678`                            |
| Letta            | `8283`                            |
| Ollama           | `11434`                           |
| Kokoro           | `8880`                            |

---

## Default Credentials

All credentials are defined in `.env`. Defaults after `p4n4 init`:

| Service  | Username | Password        |
|----------|----------|-----------------|
| InfluxDB | `admin`  | `adminpassword` |
| Grafana  | `admin`  | `adminpassword` |
| n8n      | `admin`  | `adminpassword` |

---

## Resources

- [p4n4.com](https://p4n4.com) — Platform overview and architecture guide
- [p4n4-docker](https://github.com/raisga/p4n4-docker) — Docker Compose source for all services
- [MING Stack Tutorial](https://github.com/ArthurKretzer/tutorial-p4n4-stack) — IIoT data stack tutorial (XIV SBESC, 2024)
- [MING Stack with Edge Impulse](https://www.edgeimpulse.com/blog/accelerate-edge-ai-application-development-with-the-p4n4-stack-edge-impulse/) — Integration guide
- [Edge Impulse Linux SDK (Python)](https://github.com/edgeimpulse/linux-sdk-python)
- [Eclipse Mosquitto](https://mosquitto.org/)
- [InfluxDB Documentation](https://docs.influxdata.com/)
- [Node-RED Documentation](https://nodered.org/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [n8n Documentation](https://docs.n8n.io/)
- [Letta Documentation](https://docs.letta.com/)
- [Ollama](https://github.com/ollama/ollama)
- [Kokoro FastAPI](https://github.com/remsky/Kokoro-FastAPI)

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).
