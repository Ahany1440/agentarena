"""Load arena.yaml into ArenaConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentarena.models import ArenaConfig


def load_config(path: str | Path = "arena.yaml") -> ArenaConfig:
    p = Path(path)
    return ArenaConfig.model_validate(yaml.safe_load(p.read_text()) or {}) if p.exists() else ArenaConfig()
