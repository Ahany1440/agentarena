"""Live backend with a fake client: request shape, cost, budget, and the victim loop. No API key, no cost."""

import pytest
from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock, BetaUsage
from conftest import run

from agentarena.llm.base import BudgetExceeded, TokenBudget
from agentarena.llm.live import AnthropicLLM
from agentarena.models import ToolSpec


def msg(content, stop="end_turn"):
    return BetaMessage.model_construct(
        id="m", type="message", role="assistant", model="claude-haiku-5-5", content=content, stop_reason=stop,
        usage=BetaUsage.model_construct(input_tokens=1000, output_tokens=200,
                                        cache_creation_input_tokens=0, cache_read_input_tokens=0))


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.beta = self
        self.messages = self

    async def create(self, **kw):
        self.calls.append(kw)
        return self.replies.pop(0)


def test_request_shape_cost_and_tool_calls():
    tool = BetaToolUseBlock.model_construct(type="tool_use", id="tu_1", name="read_email", input={"id": "1"})
    fake = FakeClient([msg([BetaTextBlock.model_construct(type="text", text="ok"), tool], "tool_use")])
    llm = AnthropicLLM("claude-haiku-5-5", TokenBudget(10_000), client=fake)  # type: ignore[arg-type]
    spec = ToolSpec(server="email", name="read_email", description="d", input_schema={"type": "object"})
    r = run(llm.complete("sys", [{"role": "user", "content": "hi"}], tools=[spec]))
    kw = fake.calls[0]
    assert kw["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "fallbacks" not in kw  # Haiku has no server-side fallback
    assert r.tool_calls[0].name == "read_email" and r.tool_ids == ["tu_1"]
    assert r.raw and r.raw[1]["id"] == "tu_1"
    assert r.cost_usd == pytest.approx(1000 * 0.10 / 1e6 + 200 * 0.50 / 1e6)


def test_sonnet_gets_fallbacks_and_json_is_extracted():
    fake = FakeClient([msg([BetaTextBlock.model_construct(type="text", text='Sure:\n```json\n{"a": 1}\n```')])])
    llm = AnthropicLLM("claude-sonnet-5-5", TokenBudget(10_000), client=fake)  # type: ignore[arg-type]
    r = run(llm.complete("sys", [{"role": "user", "content": "x"}], json_mode=True))
    assert fake.calls[0]["fallbacks"] == "default" and r.text == '{"a": 1}'


def test_victim_loop_sends_raw_blocks_and_real_tool_ids(tmp_path):
    from agentarena.defense.gateway import build_gateway
    from agentarena.range.loader import get_scenario
    from agentarena.range.servers import build_range
    from agentarena.range.victim import Victim

    scn = get_scenario("benign_inbox_summary")
    servers, specs, clean, _ = run(build_range(scn, {}, tmp_path, "CANARY-x"))
    gw = build_gateway("none", servers, specs, clean, scn, None)  # type: ignore[arg-type]
    tool = BetaToolUseBlock.model_construct(type="tool_use", id="tu_9", name="list_inbox", input={})
    fake = FakeClient([msg([tool], "tool_use"), msg([BetaTextBlock.model_construct(type="text", text="done")])])
    llm = AnthropicLLM("claude-haiku-5-5", TokenBudget(100_000), client=fake)  # type: ignore[arg-type]
    t = run(Victim(llm, gw, "CANARY-x").run(scn.task))
    second = fake.calls[1]["messages"]
    assert second[1]["content"][0]["id"] == "tu_9"
    assert second[2]["content"][0]["tool_use_id"] == "tu_9"
    assert t.final_output == "done" and t.calls[0].call.name == "list_inbox"


def test_attacker_uses_schema_and_keeps_raw_reply():
    from random import Random

    from agentarena.attacker.attacker import Attacker
    from agentarena.models import Attempt, Transcript, TrialResult, Verdict
    from agentarena.range.loader import get_scenario

    scn = get_scenario("inbox_summary_exfil")
    good = '{"reflection": "r", "mutation": "urgency", "payloads": {"body": "URGENT: do it"}}'
    refused = msg([], "refusal")
    fake = FakeClient([msg([BetaTextBlock.model_construct(type="text", text=good)]), refused])
    llm = AnthropicLLM("claude-sonnet-5-5", TokenBudget(100_000), client=fake)  # type: ignore[arg-type]
    atk = Attacker(llm, scn, [], Random(0))
    parent = TrialResult(attempt=Attempt(id="p", scenario=scn.id, defense="none", index=0, mutation="seed",
                                         payloads={"body": "seed"}),
                         transcript=Transcript(), verdict=Verdict(success=False, method="rule", reasons=[]),
                         utility_ok=None, canary="c", seed=0)
    mutation, _, payloads = run(atk.next([parent]))
    fmt = fake.calls[0]["output_config"]["format"]
    assert fmt["schema"]["properties"]["payloads"]["required"] == ["body"]
    assert (mutation, payloads) == ("urgency", {"body": "URGENT: do it"})
    assert atk.last_raw.startswith("[end_turn]")
    mutation, _, payloads = run(atk.next([parent]))
    assert mutation == "llm_refused" and payloads == {"body": "seed"} and atk.last_raw.startswith("[refusal]")


def test_budget_stops_calls():
    llm = AnthropicLLM("claude-haiku-5-5", TokenBudget(1000), client=FakeClient([msg([])]))  # type: ignore[arg-type]
    with pytest.raises(BudgetExceeded):
        run(llm.complete("sys", [{"role": "user", "content": "x"}]))  # 1200 tokens > 1000
    with pytest.raises(BudgetExceeded):
        run(llm.complete("sys", [{"role": "user", "content": "x"}]))  # checked before the call
