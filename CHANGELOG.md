# Changelog

All notable changes to `p4n4` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[Unreleased]: https://github.com/raisga/p4n4-cli/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/raisga/p4n4-cli/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raisga/p4n4-cli/releases/tag/v0.1.0
