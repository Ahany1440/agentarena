"""MCP gateway that sits between the victim and the fake servers."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from agentarena.defense.layers import (
    Allowlist,
    DescriptionScanner,
    GatewayContext,
    Layer,
    Monitor,
    Spotlighter,
    TaintTracker,
    pin,
)
from agentarena.llm.base import LLM
from agentarena.models import CallRecord, Scenario, ToolCall, ToolSpec
from agentarena.range.servers import call_server

LAYER_NAMES = ["scanner", "allowlist", "taint", "monitor", "spotlight"]  # order used by "all"
DEFENSE_CONFIGS: dict[str, list[str]] = {"none": [], **{n: [n] for n in LAYER_NAMES}, "all": LAYER_NAMES}


class Gateway:
    def __init__(self, servers: dict[str, MCPServer], specs: dict[str, ToolSpec],
                 layers: list[Layer], ctx: GatewayContext):
        self.servers, self.specs, self.layers, self.ctx = servers, specs, layers, ctx

    def list_tools(self) -> list[ToolSpec]:
        tools = list(self.specs.values())
        for layer in self.layers:
            tools = layer.on_tools(tools, self.ctx)
        return tools

    async def call(self, call: ToolCall) -> CallRecord:
        visible = {t.name: t for t in self.list_tools()}
        spec = visible.get(call.name)
        if spec is None:
            return CallRecord(call=call, result="BLOCKED: unknown tool", blocked_by="unknown_tool")
        for layer in self.layers:
            reason = await layer.on_call(call, spec, self.ctx)
            if reason:
                return CallRecord(call=call, result=f"BLOCKED: {reason}", blocked_by=layer.name)
        result = await call_server(self.servers[spec.server], call.name, call.args)
        for layer in self.layers:
            result = layer.on_result(call, spec, result, self.ctx)
        return CallRecord(call=call, result=result)


def build_gateway(name: str, servers: dict[str, MCPServer], specs: dict[str, ToolSpec],
                  clean_specs: dict[str, ToolSpec], scn: Scenario, monitor_llm: LLM) -> Gateway:
    make = {"scanner": DescriptionScanner, "allowlist": Allowlist, "taint": TaintTracker,
            "spotlight": Spotlighter, "monitor": lambda: Monitor(monitor_llm)}
    ctx = GatewayContext(task=scn.task, policy=scn.policy,
                         pins={n: pin(s.description) for n, s in clean_specs.items()})
    return Gateway(servers, specs, [make[n]() for n in DEFENSE_CONFIGS[name]], ctx)
