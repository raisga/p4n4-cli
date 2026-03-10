"""Remote source URLs for p4n4 stack repos, loaded from sources.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

_data: dict = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text())

iot_repo_url: str = _data["iot_repo_url"]
ai_repo_url: str = _data["ai_repo_url"]
edge_repo_url: str = _data["edge_repo_url"]
