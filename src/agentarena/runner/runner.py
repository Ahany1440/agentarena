"""Run trials, attacker cells and the scenario x defense matrix, with resume from SQLite."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path
from random import Random

from agentarena.attacker.attacker import Attacker, PayloadLibrary
from agentarena.defense.gateway import build_gateway
from agentarena.judge.judge import judge, utility_ok
from agentarena.llm import get_backend
from agentarena.llm.base import BudgetExceeded, TokenBudget
from agentarena.models import ArenaConfig, Attempt, Scenario, TrialResult
from agentarena.range.servers import build_range, clean_tool_list
from agentarena.range.victim import Victim
from agentarena.runner.store import Store


def trial_seed(base: int, scenario: str, defense: str, idx: int) -> int:
    return int(hashlib.sha256(f"{base}:{scenario}:{defense}:{idx}".encode()).hexdigest()[:8], 16)


async def run_trial(scn: Scenario, attempt: Attempt, defense: str, cfg: ArenaConfig, mode: str,
                    budget: TokenBudget, seed: int) -> TrialResult:
    canary = f"CANARY-{Random(seed).getrandbits(48):012x}"
    with tempfile.TemporaryDirectory() as d:
        servers, specs, clean, state = await build_range(scn, attempt.payloads, Path(d), canary)
        monitor = get_backend(mode, "monitor", cfg, budget)
        victim_llm = get_backend(mode, "victim", cfg, budget, scn=scn, seed=seed)
        judge_llm = get_backend(mode, "judge", cfg, budget)
        gw = build_gateway(defense, servers, specs, clean, scn, monitor)  # type: ignore[arg-type]
        t = await Victim(victim_llm, gw, canary).run(scn.task)  # type: ignore[arg-type]
        verdict = await judge(judge_llm, scn, t, state, canary)  # type: ignore[arg-type]
    cost = sum(getattr(b, "cost_usd", 0.0) for b in (monitor, victim_llm, judge_llm))
    return TrialResult(attempt=attempt, transcript=t, verdict=verdict, utility_ok=utility_ok(scn, t),
                       canary=canary, seed=seed, cost_usd=cost)


async def run_cell(scn: Scenario, defense: str, cfg: ArenaConfig, mode: str, budget: TokenBudget,
                   store: Store, lib: PayloadLibrary, run_id: str) -> None:
    """Benign: `attempts` plain trials. Attack: an attacker loop of `attempts`. Resumes from stored rows."""
    history = [r for r in store.results(run_id) if r.attempt.scenario == scn.id and r.attempt.defense == defense]
    benign = scn.attack_class == "benign"
    attacker = None if benign else Attacker(
        get_backend(mode, "attacker", cfg, budget), scn, clean_tool_list(scn),
        Random(f"{cfg.seed}:{scn.id}:{defense}:{len(history)}"),
    )
    for idx in range(len(history), cfg.attempts):
        budget.check()
        parent: str | None = None
        spent = getattr(attacker and attacker.llm, "cost_usd", 0.0)
        if attacker is None:
            mutation, payloads = "none", {}
        elif idx == 0:
            mutation, payloads = attacker.first()
        else:
            mutation, parent, payloads = await attacker.next(history)
        attacker_cost = getattr(attacker and attacker.llm, "cost_usd", 0.0) - spent
        attempt = Attempt(id=f"{scn.id}:{defense}:{idx}", scenario=scn.id, defense=defense, index=idx,
                          parent_id=parent, mutation=mutation, payloads=payloads,
                          attacker_raw=attacker.last_raw if attacker else "")
        r = await run_trial(scn, attempt, defense, cfg, mode, budget, trial_seed(cfg.seed, scn.id, defense, idx))
        r.cost_usd += attacker_cost  # the attacker's calls belong to this trial's cost too
        store.save(run_id, r)
        if not benign:
            lib.add(r)
        history.append(r)


async def run_matrix(scenarios: list[Scenario], defenses: list[str], cfg: ArenaConfig, mode: str,
                     run_id: str, budget: TokenBudget | None = None) -> bool:
    """Run every scenario x defense cell. Returns False if the token budget stopped the run."""
    budget = budget or TokenBudget(cfg.budget_tokens)
    store, lib = Store(cfg.db_path), PayloadLibrary(Path(cfg.payloads_path))
    sem = asyncio.Semaphore(cfg.concurrency)
    stopped = False

    async def cell(scn: Scenario, d: str) -> None:
        nonlocal stopped
        async with sem:
            try:
                await run_cell(scn, d, cfg, mode, budget, store, lib, run_id)
            except BudgetExceeded:  # every other cell stops at its next budget.check()
                stopped = True

    await asyncio.gather(*(cell(s, d) for s in scenarios for d in defenses))
    return not stopped
