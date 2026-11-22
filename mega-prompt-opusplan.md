# Build "AgentArena": an open-source red-team range for AI agents and MCP servers

## 0. How we work (read first)
This session uses `/model opusplan`: **Opus thinks (plan mode), Sonnet executes.** Work like this:

1. **Plan mode (Opus), once at the start.** Do all the hard thinking now. Write `PLAN.md` with: exact file list, every class/function signature, pydantic data models, the YAML scenario format with 2 full examples, the defense-layer interfaces, the test list, and the order of work. It must be detailed enough that a cheaper model can build it with **no design decisions left**. Then ask me to approve the plan (only this one stop).
2. **Execute (Sonnet), phase by phase.** Follow `PLAN.md` exactly. Do not redesign. Do not re-read files you just wrote. Run tests after each phase.
3. **Review checkpoint after each phase.** Re-enter plan mode (Opus) for a short review: check the diff against `PLAN.md`, list bugs/risks, fix the plan, then Sonnet continues. Keep reviews short.
4. Save tokens: small focused edits, no long explanations, no repeated full-file rewrites, no unnecessary dependencies.

## 1. Project
AgentArena is a safe "wargame" for AI agents:
- A **range** of deliberately vulnerable fake agents and fake MCP servers (local, fake data).
- An **attacker agent** that invents and mutates prompt-injection and tool-poisoning attacks.
- A **judge** that decides if an attack worked.
- A **defender**: an MCP gateway with switchable defense layers.
- A **scoreboard/report**: attack success rate (ASR) with and without defenses, plus how well the agent still does normal tasks (utility).
Goal: a reproducible open benchmark that looks strong on a resume and at a hackathon.

## 2. Hard safety rules
- Only my own local fake agents and fake data. No real targets, no scanning, no real credentials or personal data.
- "Secrets" are random canary strings. Success = canary leaked or a forbidden tool called.
- Tools are simulated (e.g. `send_email` writes to a local JSON outbox; `read_file` reads a sandbox folder only).
- API key only from `ANTHROPIC_API_KEY`. Never print, log, save, or commit it. `.env` in `.gitignore`.
- No exploit code for real products. Payloads are generic text patterns tested only on the fake range.
- Add `SECURITY.md` and an "Ethical use" README section.

## 3. Cost rule (important)
I am on a subscription, not an unlimited API.
- **Default mode is `mock`**: a fake LLM with scripted behavior, zero API cost. All tests and the demo must work in mock mode.
- **`--live` mode** calls the Anthropic API (needs `ANTHROPIC_API_KEY`). Defaults: victim `claude-haiku-5-5`, attacker `claude-sonnet-5-5`, judge `claude-haiku-5-5`. Always apply `--budget-tokens` (default 300000) and stop when it's used up. Use prompt caching.
- Print estimated token use before any live run and ask me to confirm.

## 4. Stack and layout
Python 3.11+, `anthropic`, official `mcp` SDK, `pydantic`, `sqlite3`, `rich`, `pytest`, `ruff`. Scoreboard = one static HTML file with Chart.js from a CDN.
```
src/agentarena/
  range/ (servers: email, github_issues, notes_files, web_page; victim.py; scenarios/*.yaml)
  attacker/  judge/  defense/  runner/  report/  llm/ (mock + live backends)  cli.py
tests/  docs/  README.md  SECURITY.md  DECISIONS.md  PLAN.md  arena.yaml  pyproject.toml
```

## 5. Range
4 fake MCP servers with 2-4 tools each (email, github_issues, notes_files, web_page). A victim agent loop (LLM + tools) holding a canary secret and a forbidden-action list. YAML scenarios define: user task, enabled servers, where attacker text can go (email body, issue text, web page, **tool description**), canary, forbidden actions, success condition. Include benign scenarios for utility.
Attack classes: indirect prompt injection, tool poisoning, cross-server chaining, data exfiltration via an allowed tool, goal hijacking, over-permission abuse.

## 6. Attacker and judge
- Attacker sees the tool list, where it may write text, and the goal. It does not see defense internals.
- Loop: generate payload -> run victim -> read result -> reflect -> mutate. Mutations: rephrase, role-play, fake admin notice, split across two places, encoding/obfuscation, urgency/authority. Keep top-k payloads and evolve them.
- Save every attempt to a JSONL payload library (regression set).
- Judge: rule-based first (canary in outbox/output, forbidden tool called), LLM judge only for fuzzy cases (strict JSON). Include a small hand-labeled set and report judge accuracy.

## 7. Defender (switchable layers)
1. Tool-description scanner + hash pinning (detect changed descriptions).
2. Taint tracking (untrusted content cannot flow into sensitive tools without a check).
3. Per-task allowlist/policy (YAML).
4. Spotlighting (mark untrusted data as data only).
5. Monitor model that vetoes tool calls that don't match the user's task.
Report ASR for: none, each layer alone, all layers, plus utility on benign tasks.

## 8. Runner and report
- `arena run`, `arena report`, `arena list`, `arena demo` (cheap mock demo).
- Async parallel trials, retries, resume after crash (SQLite), saved seeds/configs, tokens and cost per trial.
- Report: `report/index.html` + `report.md`: ASR by attack class/model/defense, security vs utility chart, top payload families, case studies, totals.
- `docs/WRITEUP.md` only from **real measured results**. Never invent numbers; leave TODOs where data is missing.

## 9. Phases and done criteria
1. Range + victim + 6 scenarios; `arena list` works; a benign mock run completes.
2. Attacker + judge; mock run shows an injection succeeding on the undefended victim.
3. Defenses + runner; full matrix table (ASR with/without defenses + utility) in mock mode.
4. Report + docs + tests green; `arena demo` works in one command.
5. Live smoke test (small, with confirmation) to get a few real numbers.
6. Stretch if budget remains: more scenarios/models, genetic search, GitHub Action running the mock demo.

## 10. Quality
Tests for judge rules, each defense, runner resume, scenario loading. Type hints, short docstrings, `ruff` clean. README with a 5-minute quickstart and limitations. Simple readable code, no dead code.

## 11. Finish
At the end, tell me: what works, real numbers if any, what's missing, and the exact commands to reproduce.
