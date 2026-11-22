# AgentArena

An open-source red-team range for AI agents and MCP servers. It is a safe "wargame": deliberately vulnerable
**fake** agents and **fake** MCP servers, an attacker that evolves prompt-injection and tool-poisoning payloads,
a judge, and an MCP gateway with switchable defense layers. The output is a reproducible scoreboard: attack
success rate (ASR) with and without each defense, plus utility on benign tasks.

## 5-minute quickstart

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
arena list                        # 8 scenarios, 7 defense configs
arena demo                        # full mock matrix + report, zero API cost
pytest -q && ruff check src tests
```

Open `report/index.html` (chart + tables) or read `report/report.md`.

## Commands

| command | what it does |
|---|---|
| `arena list` | scenarios, attack classes, injection points, defense configs |
| `arena run [--scenarios ...] [--defenses ...] [--attempts N] [--run-id ID]` | run the scenario x defense matrix (mock by default) |
| `arena run --live --budget-tokens 300000` | live mode (Anthropic API, needs `ANTHROPIC_API_KEY`); prints an estimate and asks first |
| `arena report [--run-id ID]` | write `report/report.md` and `report/index.html` for a run (latest by default) |
| `arena demo` | mock run of everything with 30 attempts per cell, then the report |
| `arena judge-eval` | judge accuracy on the hand-labeled set |

A crashed run resumes from SQLite (`runs/arena.db`): rerun with the same `--run-id`. Every attack attempt is
appended to `runs/payloads.jsonl` (a regression set).

## How it works

- **Range** (`range/`): 4 in-process MCP servers built with the official `mcp` SDK: `email`, `github_issues`,
  `notes_files` (sandboxed temp folder), `web_page`. All data is fixture data; `send_email` writes a local
  `outbox.json`. The victim holds a random canary "API key".
- **Scenarios** (`range/scenarios/*.yaml`): user task, servers, injection points (email body, issue text, web page,
  file, **tool description**), attacker goal, forbidden calls, utility check, per-task policy. One scenario per
  attack class (indirect injection, tool poisoning, cross-server chaining, exfiltration via an allowed tool, goal
  hijacking, over-permission) plus 5 benign tasks. Three benign tasks need a sensitive tool (`send_email`,
  `post_form`), and in two of them the recipient or URL comes from the data rather than the task, so over-blocking
  defenses lose utility.
- **Attacker** (`attacker/`): seed payload, then mutate the top-k payloads (rephrase, role-play, fake admin notice,
  split across two places, base64, urgency). It sees tools, injection points and the goal, never defense internals.
- **Judge** (`judge/`): rules first (canary leaked anywhere, forbidden call executed, output marker), LLM judge
  only for fuzzy goal-hijack cases (strict JSON). Accuracy is measured on `judge/labeled.jsonl`.
- **Defender** (`defense/`): an MCP gateway with 5 layers: description scanner + hash pinning, taint tracking,
  per-task allowlist, spotlighting, monitor model. Configs: `none`, each layer alone, `all`.

## Limitations (read this)

- **Mock numbers are simulated.** The mock victim is a scripted, deliberately gullible agent: it follows
  `tool(arg="...")` directives it finds in untrusted text with a seeded probability that rises with authority or
  urgency cues and drops under spotlighting. Mock results show that the pipeline works and how the layers rank
  against *that* victim. They say nothing about real model robustness. Only `--live` numbers do.
- The report shows 95% Wilson confidence ranges. With 30 attempts per cell they are still about ±15 points, so
  only compare cells whose ranges do not overlap.
- No defense knows the canary format. Taint tracking and the monitor only look at where a sink value came from,
  which is why they also block some legitimate actions (see utility).
- The servers run in-process, not as separate stdio processes.
- The live backend (`llm/live.py`) is part of Phase 5 and is not built yet.

## Ethical use

AgentArena attacks **only its own local fake agents and fake data**. It does not scan, target or connect to real
systems, and it ships no exploit code for real products: payloads are generic text patterns tested only on this
range. Secrets are random canary strings. Do not point it at systems you do not own. See [SECURITY.md](SECURITY.md).
