"""LLM backends: mock (default, free) and live (Anthropic API)."""

from __future__ import annotations

from typing import Literal

from agentarena.llm.base import LLM, TokenBudget
from agentarena.llm.mock import MockJudge, MockMonitor, MockVictim
from agentarena.models import ArenaConfig, Scenario

Role = Literal["victim", "attacker", "judge", "monitor"]


def get_backend(mode: str, role: Role, cfg: ArenaConfig, budget: TokenBudget,
                scn: Scenario | None = None, seed: int = 0) -> LLM | None:
    """Return the LLM for a role. Mock attacker is None (the attacker uses scripted mutations)."""
    if mode == "mock":
        if role == "victim":
            assert scn is not None
            return MockVictim(scn.task_tools, seed)
        return {"judge": MockJudge, "monitor": MockMonitor}.get(role, lambda: None)()
    from agentarena.llm.live import AnthropicLLM

    model = {"victim": cfg.victim_model, "attacker": cfg.attacker_model}.get(role, cfg.judge_model)
    return AnthropicLLM(model, budget)
