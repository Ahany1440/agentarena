"""Load and validate YAML scenarios."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentarena.models import Scenario

SCENARIO_DIR = Path(__file__).parent / "scenarios"


def load_scenarios(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    scns = [Scenario.model_validate(yaml.safe_load(p.read_text())) for p in sorted(directory.glob("*.yaml"))]
    ids = [s.id for s in scns]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate scenario ids: {ids}")
    return scns


def get_scenario(scenario_id: str) -> Scenario:
    for s in load_scenarios():
        if s.id == scenario_id:
            return s
    raise KeyError(scenario_id)
