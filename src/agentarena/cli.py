"""`arena` command line: list, run, report, demo, judge-eval."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agentarena.config import load_config
from agentarena.defense.gateway import DEFENSE_CONFIGS
from agentarena.judge.judge import eval_judge
from agentarena.llm.base import TokenBudget
from agentarena.llm.mock import MockJudge
from agentarena.models import ArenaConfig
from agentarena.range.loader import load_scenarios
from agentarena.report.report import aggregate, write_html, write_markdown
from agentarena.runner.runner import run_matrix
from agentarena.runner.store import Store

console = Console()
TOKENS_PER_TRIAL = 6000  # rough live estimate: victim steps + judge/monitor calls


def cmd_list(cfg: ArenaConfig, args: argparse.Namespace) -> None:
    t = Table("id", "class", "servers", "injection points")
    for s in load_scenarios():
        t.add_row(s.id, s.attack_class, ",".join(s.servers), ",".join(p.kind for p in s.injection_points) or "-")
    console.print(t)
    console.print(f"defenses: {', '.join(DEFENSE_CONFIGS)}")


def print_summary(agg: dict) -> None:
    t = Table("metric", *agg["defenses"], title=f"AgentArena ({agg['mode']})")
    def fmt(x: float | None) -> str:
        return "-" if x is None else f"{x:.0%}"
    t.add_row("ASR (attacks)", *[fmt(agg["asr"][d]) for d in agg["defenses"]])
    t.add_row("Utility (benign)", *[fmt(agg["utility"][d]) for d in agg["defenses"]])
    console.print(t)


def cmd_report(cfg: ArenaConfig, args: argparse.Namespace) -> None:
    store = Store(cfg.db_path)
    run_id = args.run_id or next(iter(store.runs()), None)
    if run_id is None:
        sys.exit("no runs found; run `arena demo` or `arena run` first")
    agg = aggregate(store.results(run_id), asyncio.run(eval_judge(MockJudge())))
    out = Path(cfg.report_dir)
    write_markdown(agg, out / "report.md")
    write_html(agg, out / "index.html")
    print_summary(agg)
    console.print(f"run {run_id}: wrote {out / 'report.md'} and {out / 'index.html'}")


def cmd_run(cfg: ArenaConfig, args: argparse.Namespace) -> None:
    if args.attempts:
        cfg.attempts = args.attempts
    if args.concurrency:
        cfg.concurrency = args.concurrency
    if args.budget_tokens:
        cfg.budget_tokens = args.budget_tokens
    mode = "live" if args.live else "mock"
    scns = load_scenarios()
    if args.scenarios:
        scns = [s for s in scns if s.id in args.scenarios]
    defenses = args.defenses or cfg.defenses
    unknown = set(defenses) - set(DEFENSE_CONFIGS)
    if unknown or not scns:
        sys.exit(f"unknown defenses {sorted(unknown)} or no matching scenarios")
    run_id = args.run_id or f"{mode}-{time.strftime('%Y%m%d-%H%M%S')}"
    if mode == "live":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("--live needs ANTHROPIC_API_KEY in the environment")
        est = len(scns) * len(defenses) * cfg.attempts * TOKENS_PER_TRIAL
        console.print(f"Live run: {len(scns)} scenarios x {len(defenses)} defenses x {cfg.attempts} attempts "
                      f"~ {est:,} tokens (budget cap {cfg.budget_tokens:,}).")
        if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
            sys.exit("cancelled")
    budget = TokenBudget(cfg.budget_tokens)
    finished = asyncio.run(run_matrix(scns, defenses, cfg, mode, run_id, budget))
    if not finished:
        console.print(f"[yellow]Token budget used up ({budget.used:,}); resume with --run-id {run_id}[/]")
    console.print(f"run {run_id} done ({mode}); tokens used {budget.used:,}")
    args.run_id = run_id
    cmd_report(cfg, args)


def cmd_demo(cfg: ArenaConfig, args: argparse.Namespace) -> None:
    ns = argparse.Namespace(attempts=None,concurrency=None, budget_tokens=None, live=False, scenarios=None,
                            defenses=None, run_id=f"demo-{time.strftime('%Y%m%d-%H%M%S')}", yes=True)
    cmd_run(cfg, ns)


def cmd_judge_eval(cfg: ArenaConfig, args: argparse.Namespace) -> None:
    console.print(f"judge accuracy on hand-labeled set: {asyncio.run(eval_judge(MockJudge())):.0%}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="arena", description="AgentArena: red-team range for AI agents (fake targets)")
    p.add_argument("--config", default="arena.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list scenarios and defenses")
    r = sub.add_parser("run", help="run the scenario x defense matrix")
    r.add_argument("--scenarios", nargs="+")
    r.add_argument("--defenses", nargs="+")
    r.add_argument("--attempts", type=int)
    r.add_argument("--concurrency", type=int)
    r.add_argument("--budget-tokens", type=int)
    r.add_argument("--live", action="store_true", help="call the Anthropic API (costs tokens)")
    r.add_argument("--run-id", help="reuse to resume a crashed run")
    r.add_argument("--yes", action="store_true", help="skip the live confirmation prompt")
    rp = sub.add_parser("report", help="write report.md and index.html")
    rp.add_argument("--run-id")
    sub.add_parser("demo", help="cheap mock demo: run everything and write the report")
    sub.add_parser("judge-eval", help="judge accuracy on the hand-labeled set")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    {"list": cmd_list, "run": cmd_run, "report": cmd_report, "demo": cmd_demo,
     "judge-eval": cmd_judge_eval}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
