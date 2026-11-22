"""Live backend: real Claude models through the Anthropic API. Costs money; always budget-capped.

The API key is read by the SDK from ANTHROPIC_API_KEY. It is never logged or stored here.
"""

from __future__ import annotations

import re

import anthropic

from agentarena.llm.base import LLMResponse, TokenBudget
from agentarena.models import ToolCall, ToolSpec

# USD per 1M tokens (input, output). Cache reads bill at 0.1x input, cache writes at 1.25x.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
# Models with server-side refusal fallback; Haiku has none, so a refusal there just ends the turn.
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}
JSON_OBJECT = re.compile(r"\{.*\}", re.S)


class AnthropicLLM:
    def __init__(self, model: str, budget: TokenBudget, effort: str | None = None,
                 max_tokens: int = 4096, client: anthropic.AsyncAnthropic | None = None):
        self.model, self.budget, self.effort, self.max_tokens = model, budget, effort, max_tokens
        self.client = client or anthropic.AsyncAnthropic(max_retries=4)  # SDK retries 429/5xx with backoff
        self.cost_usd = 0.0

    async def complete(self, system: str, messages: list[dict], tools: list[ToolSpec] | None = None,
                       json_mode: bool = False, schema: dict | None = None) -> LLMResponse:
        self.budget.check()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
        }
        if tools:
            defs = [{"name": t.name, "description": t.description, "input_schema": t.input_schema or
                     {"type": "object", "properties": {}}} for t in tools]
            defs[-1]["cache_control"] = {"type": "ephemeral"}
            kwargs["tools"] = defs
        output_config: dict = {}
        if self.effort:
            output_config["effort"] = self.effort
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if output_config:
            kwargs["output_config"] = output_config
        if self.model in FALLBACK_MODELS:
            kwargs |= {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        resp = await self.client.beta.messages.create(**kwargs)

        u = resp.usage
        cache_w, cache_r = u.cache_creation_input_tokens or 0, u.cache_read_input_tokens or 0
        tokens_in = u.input_tokens + cache_w + cache_r
        p_in, p_out = PRICES.get(self.model, (4.00, 20.00))
        cost = (u.input_tokens + 1.25 * cache_w + 0.1 * cache_r) * p_in / 1e6 + u.output_tokens * p_out / 1e6
        self.cost_usd += cost
        self.budget.charge(tokens_in + u.output_tokens)

        text = "".join(b.text for b in resp.content if b.type == "text")
        if json_mode and (m := JSON_OBJECT.search(text)):
            text = m.group(0)  # strip prose or ```json fences around the object
        uses = [b for b in resp.content if b.type == "tool_use"]
        return LLMResponse(
            text=text,
            tool_calls=[ToolCall(name=b.name, args=dict(b.input)) for b in uses],
            tool_ids=[b.id for b in uses],
            # passed back unchanged so thinking blocks and tool_use ids stay valid on the next turn
            raw=[b.model_dump(mode="json", exclude_none=True) for b in resp.content],
            stop_reason=resp.stop_reason or "",
            tokens_in=tokens_in,
            tokens_out=u.output_tokens,
            cost_usd=cost,
        )
