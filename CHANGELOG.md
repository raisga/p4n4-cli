# Changelog

All notable changes to `p4n4` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed

- `p4n4 init --layer iot,ai` (and `--layer all`) no longer crashes on file collisions:
  multi-layer projects now scaffold each layer into its own subdirectory
  (`<project>/iot/`, `<project>/ai/`) with its own compose file, config, and `.env`,
  matching how the stacks are designed to run (separate Compose projects sharing the
  `p4n4-net` network). Single-layer projects keep the flat layout.

### Added

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

### Changed

- Shared, framework-agnostic code extracted into the new [`p4n4-lib`](https://github.com/raisga/p4n4-lib)
  package, now a dependency: manifest, dotenv, Docker Compose wrappers, layer registry
  (repo URLs, copy paths, required files/env keys), scaffolding, validation, and secret
  generation all live in `p4n4_lib`
- `p4n4/utils/`, `p4n4/sources.py`, and `p4n4/sources.yaml` removed in favour of `p4n4_lib`
- Duplicate token generators in `init`/`secret` unified as `p4n4_lib.secrets`
- "No .p4n4.json found" error message unified across commands via `p4n4.project.require_manifest`
- Tests locate local stack checkouts via sibling repos (CI) or `stacks/<name>` (monorepo)

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

[Unreleased]: https://github.com/raisga/p4n4-cli/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/raisga/p4n4-cli/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raisga/p4n4-cli/releases/tag/v0.1.0
