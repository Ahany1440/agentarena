# Decisions

Short log of choices that are not obvious from the code.

1. **In-process MCP servers.** The servers use the official `mcp` 2.x SDK (`MCPServer`) but are called in
   process (`server.call_tool`). This avoids subprocess management and keeps tests fast. Upgrade to a stdio client
   if cross-process isolation matters.
2. **Mock-first.** Every test and the demo run on scripted LLMs at zero cost. The mock victim's obedience model
   (base 0.35, +0.15 per cue, x0.25 under spotlighting) is a design assumption, so mock reports are labelled
   SIMULATED.
3. **The mock victim knows the task plan** (`task_tools` in the scenario) so that utility is measurable without a
   real model; live mode ignores `task_tools`.
4. **The scenario loader is `range/loader.py`** (the plan said `range/scenarios.py`), because a module named
   `scenarios.py` next to the `scenarios/` YAML folder confused tooling.
5. **`say(text="...")` is a pseudo-directive** used by the goal-hijack scenario: the mock victim adds the text to
   its answer instead of calling a tool.
6. **Adaptive attacker per defense config.** The attacker evolves separately in each cell, using only outcomes
   (success or blocked), never defense names.
7. **ASR is measured per attempt** (successful attempts / attempts), not "any success per scenario".
8. **The judge measures the LLM path with the mock judge** in `judge-eval`; live judge accuracy is a TODO for
   Phase 5.
9. **Ruff line length is 120** (the plan did not specify one); 110 forced awkward wrapping in the HTML template.
