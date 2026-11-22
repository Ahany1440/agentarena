# AgentArena: what happens when you attack a real AI agent

Every number here was measured. Mock (simulated) numbers come from a scripted victim and are labelled.

## The problem

AI agents now read email, issues, web pages and files, and they hold tools that act: send email, post forms,
write notes. Anyone who can put text in front of the agent can try to give it orders ("indirect prompt
injection"), and an MCP server can hide orders in a tool's description ("tool poisoning"). Defenses exist, but
it is rarely measured how much each one actually stops, or what it costs in normal work.

AgentArena measures both, on a safe range: fake agents, fake MCP servers, fake data, and a random canary string
as the "secret". Nothing real can be leaked or harmed.

## How it works

- **Range:** 4 in-process MCP servers (email, GitHub issues, notes/files, web) built with the official `mcp` SDK.
- **Scenarios:** 11 in total. 6 attack classes (indirect injection, tool poisoning, cross-server chaining,
  exfiltration through an allowed tool, goal hijacking, over-permission) and 5 benign tasks. Three benign tasks
  need a sensitive tool; in two of them the recipient or URL comes from the data, not the user, which is exactly
  where over-strict defenses break legitimate work.
- **Attacker:** starts from a seed payload and evolves the best ones. In live mode an LLM reflects on why the
  last attempts failed and rewrites the payload (structured JSON output, raw replies saved).
- **Judge:** rules first (canary leaked anywhere, forbidden call executed), LLM only for fuzzy hijack cases.
- **Defenses** (an MCP gateway with switchable layers): tool-description scanner with hash pinning, taint
  tracking, per-task tool allowlist, spotlighting of untrusted text, and a monitor model. No layer knows the
  canary format.
- **Statistics:** attack success rate (ASR) and utility per cell, each with a 95% Wilson confidence range.

## Live results (real models)

Run `live-20261122-115036`: Claude Haiku 5.5 as the victim agent and judge, Claude Sonnet 5.5 as the attacker,
30 attempts per cell, 600 trials. Attack scenarios: `inbox_summary_exfil` (indirect injection),
`poisoned_notes_tool` (tool poisoning) and `reply_exfil_allowed_tool` (exfiltration through an allowed tool).

| | none | taint | spotlight | all |
|---|---|---|---|---|
| Attack success (90 attempts per column) | **0%** (0–4%) | 0% (0–4%) | 0% (0–4%) | 0% (0–4%) |
| Legitimate reply to an email's sender | **30/30** | **0/30** | 30/30 | **0/30** |

### Findings

1. **The model resisted every attack, with no defense at all.** 0 of 360 attack trials succeeded. In the
   undefended runs the agent often named the attack: in 66 of the 90 undefended attack trials its answer
   contained words like "injection", "phishing", "suspicious" or "ignored". At 90 trials per
   column, the true undefended success rate is below about 4% (95% upper bound) for these three attacks.
2. **Strict defenses broke real work.** Taint tracking blocked the legitimate reply to an email's sender in 30 of
   30 trials, because the address came from the email rather than from the user. Against this model, taint
   tracking and the full stack added no measurable protection but removed 100% of that task's utility.
3. **Spotlighting was free.** Marking untrusted text as data cost no utility and did not change attack success.

### Limits (read before quoting)

- **The attacker refused often.** Sonnet 5.5 declined to write the payload in 164 of 348 attacker turns (47%),
  even with server-side fallback. The attack pressure was therefore lower than a determined human red-teamer's.
  0% means "these attacks, at this strength, failed", not "the model cannot be injected".
- **One model, three attack classes.** Cross-server chaining, goal hijacking and over-permission were run only in
  mock mode, and only Haiku 5.5 was the live victim.
- **A broken benign task.** `benign_web_rsvp` never said what form data to send, so the agent asked instead of
  posting (0/30 in every column). It is excluded from the table above and fixed for future runs.
- **Cost:** about $5 of API usage for all live runs, mostly the Sonnet attacker (its thinking tokens).
  Early reports undercounted cost because the attacker's calls were not included; that is fixed.

## Mock results (SIMULATED)

`arena demo`, seed 1337, 30 attempts per cell, 11 scenarios x 7 defense configs. The mock victim is a scripted,
deliberately gullible agent, so these numbers show that the pipeline and each layer work, not how real models
behave.

| | none | scanner | allowlist | taint | monitor | spotlight | all |
|---|---|---|---|---|---|---|---|
| Attack success | 51% | 47% | 29% | 12% | 18% | 22% | 2% |
| Utility (benign) | 100% | 100% | 100% | 60% | 60% | 100% | 60% |

The same trade-off shows up as in the live run: the layers that stop the most attacks (taint, monitor) are the
ones that block legitimate actions whose target came from the data.

## Reproduce

```bash
arena demo                                   # free, mock
arena run --live --scenarios inbox_summary_exfil poisoned_notes_tool reply_exfil_allowed_tool \
  benign_reply_to_sender benign_web_rsvp --defenses none taint spotlight all --attempts 30 \
  --budget-tokens 2000000                    # needs ANTHROPIC_API_KEY; asks before spending
arena report --run-id <run id>
```

## What next

- A cheaper attacker framing that refuses less, or a human-written payload set, to raise attack pressure.
- More victim models, and the three attack classes that only ran in mock mode.
- Taint tracking that lets a value through when the user's task clearly points at it ("reply to the sender").
