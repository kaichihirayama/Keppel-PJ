"""Loader for project configuration files (e.g. PoC target REIT list)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POC_TARGETS_PATH = PROJECT_ROOT / "config" / "poc_targets.yaml"


def load_poc_targets(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the PoC target REIT list from config/poc_targets.yaml."""
    config_path = path or POC_TARGETS_PATH
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("reits", [])
