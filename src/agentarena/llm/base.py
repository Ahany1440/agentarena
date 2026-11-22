"""LLM protocol, response model and shared token budget."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from agentarena.models import ToolCall, ToolSpec


class BudgetExceeded(RuntimeError):
    """Raised when the run's token budget is used up."""


class LLMResponse(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)  # live only: API tool_use ids
    raw: list[dict] | None = None  # live only: assistant content blocks to send back as-is
    stop_reason: str = ""  # live only: e.g. "end_turn", "tool_use", "refusal"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


class LLM(Protocol):
    async def complete(
        self, system: str, messages: list[dict], tools: list[ToolSpec] | None = None, json_mode: bool = False,
        schema: dict | None = None,  # live only: JSON schema the reply must follow (structured outputs)
    ) -> LLMResponse: ...


class TokenBudget:
    """Token budget shared by every live call in a run."""

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0

    def check(self) -> None:
        if self.used >= self.limit:
            raise BudgetExceeded(f"token budget used up ({self.used}/{self.limit})")

    def charge(self, n: int) -> None:
        self.used += n
        self.check()
