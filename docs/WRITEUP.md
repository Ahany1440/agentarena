# AgentArena: write-up

Only measured numbers go here. Mock numbers come from a scripted victim and are labelled as such.

## Setup
8 scenarios (6 attack classes + 2 benign), 7 defense configs (`none`, 5 single layers, `all`), an adaptive
attacker with 6 mutation operators, and a rule-first judge.

## Mock results (SIMULATED, `arena demo`, seed 1337, 6 attempts per cell, 336 trials)

| metric | none | scanner | allowlist | taint | monitor | spotlight | all |
|---|---|---|---|---|---|---|---|
| ASR (attacks) | 58% | 42% | 28% | 3% | 14% | 25% | 0% |
| Utility (benign) | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

Judge accuracy on the 14-case hand-labeled set: 100% (rules + mock judge).

What this does and does not show: the pipeline works end to end, and against a gullible scripted victim each layer
blocks a different slice. The scanner only stops tool poisoning, the allowlist does not stop exfiltration through
allowed tools or output hijacking, and spotlighting is the only single layer that stops output hijacking. Combining
all layers blocked every attempt with no utility loss. These are not claims about real models.

## Live results
TODO: run Phase 5 (`arena run --live --scenarios inbox_summary_exfil --defenses none all --attempts 3`) once
`ANTHROPIC_API_KEY` is set. Report real ASR, utility, tokens and cost here.

## Live judge accuracy
TODO: measure the LLM judge on `judge/labeled.jsonl` in live mode.
