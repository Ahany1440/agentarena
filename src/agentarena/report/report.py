"""Aggregate stored trials into report.md and a static Chart.js index.html."""

from __future__ import annotations

import html
import json
import math
from collections import defaultdict
from pathlib import Path

from agentarena.defense.gateway import DEFENSE_CONFIGS
from agentarena.models import TrialResult
from agentarena.range.loader import load_scenarios


def _rate(xs: list[bool]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def _ci(xs: list[bool], z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval for a success rate (sane at 0%, 100% and small n)."""
    if not xs:
        return None
    n, p = len(xs), sum(xs) / len(xs)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def aggregate(results: list[TrialResult], judge_accuracy: float | None = None) -> dict:
    classes = {s.id: s.attack_class for s in load_scenarios()}
    defenses = [d for d in DEFENSE_CONFIGS if any(r.attempt.defense == d for r in results)]
    attack = [r for r in results if classes.get(r.attempt.scenario) != "benign"]
    benign = [r for r in results if classes.get(r.attempt.scenario) == "benign"]
    cell: dict[tuple[str, str], list[bool]] = defaultdict(list)
    by_class: dict[tuple[str, str], list[bool]] = defaultdict(list)
    muts: dict[str, list[bool]] = defaultdict(list)
    for r in attack:
        ok = r.verdict.success
        cell[(r.attempt.scenario, r.attempt.defense)].append(ok)
        by_class[(classes[r.attempt.scenario], r.attempt.defense)].append(ok)
        muts[r.attempt.mutation].append(ok)
    scenarios = sorted({r.attempt.scenario for r in attack})
    class_names = sorted({classes[s] for s in scenarios})
    cases, seen = [], set()
    for r in attack:
        c = classes[r.attempt.scenario]
        if r.verdict.success and c not in seen:
            seen.add(c)
            cases.append({
                "class": c, "scenario": r.attempt.scenario, "defense": r.attempt.defense,
                "mutation": r.attempt.mutation, "payloads": r.attempt.payloads, "reasons": r.verdict.reasons,
                "calls": [f"{x.call.name}({json.dumps(x.call.args)})" + (f" BLOCKED by {x.blocked_by}"
                          if x.blocked_by else "") for x in r.transcript.calls],
            })
    live = any(r.transcript.tokens_in for r in results)
    asr = {d: [r.verdict.success for r in attack if r.attempt.defense == d] for d in defenses}
    util = {d: [bool(r.utility_ok) for r in benign if r.attempt.defense == d] for d in defenses}
    return {
        "mode": "LIVE (Anthropic API)" if live else "SIMULATED (mock LLM)",
        "defenses": defenses,
        "matrix": {s: {d: _rate(cell[(s, d)]) for d in defenses} for s in scenarios},
        "by_class": {c: {d: _rate(by_class[(c, d)]) for d in defenses} for c in class_names},
        "asr": {d: _rate(v) for d, v in asr.items()},
        "utility": {d: _rate(v) for d, v in util.items()},
        "ci": {
            "matrix": {s: {d: _ci(cell[(s, d)]) for d in defenses} for s in scenarios},
            "by_class": {c: {d: _ci(by_class[(c, d)]) for d in defenses} for c in class_names},
            "asr": {d: _ci(v) for d, v in asr.items()},
            "utility": {d: _ci(v) for d, v in util.items()},
        },
        "mutations": {m: {"n": len(v), "success_rate": _rate(v)}
                      for m, v in sorted(muts.items(), key=lambda kv: -(_rate(kv[1]) or 0))},
        "cases": cases,
        "totals": {"trials": len(results), "attack_trials": len(attack), "benign_trials": len(benign),
                   "tokens_in": sum(r.transcript.tokens_in for r in results),
                   "tokens_out": sum(r.transcript.tokens_out for r in results),
                   "cost_usd": round(sum(r.cost_usd for r in results), 4)},
        "judge_accuracy": judge_accuracy,
    }


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def _cell(x: float | None, ci: list[float] | None) -> str:
    return _pct(x) if x is None or ci is None else f"{x:.0%} ({ci[0]:.0%}–{ci[1]:.0%})"


CI_NOTE = "Brackets show the 95% confidence range (Wilson). Overlapping ranges mean no clear difference."


def _table(rows: dict[str, dict[str, float | None]], defenses: list[str], first: str,
           ci: dict[str, dict[str, list[float] | None]]) -> list[str]:
    out = [f"| {first} | " + " | ".join(defenses) + " |", "|---" * (len(defenses) + 1) + "|"]
    out += [f"| {k} | " + " | ".join(_cell(v[d], ci[k][d]) for d in defenses) + " |" for k, v in rows.items()]
    return out


def write_markdown(agg: dict, path: Path) -> None:
    d = agg["defenses"]
    t = agg["totals"]
    ci = agg["ci"]
    lines = [
        "# AgentArena report", "", f"**Mode: {agg['mode']}**", "",
        "Attack success rate (ASR): lower is better. Utility on benign tasks: higher is better.", "", CI_NOTE, "",
        "## Security vs utility", "",
        *_table({"ASR (all attacks)": agg["asr"], "Utility (benign)": agg["utility"]}, d, "metric",
                {"ASR (all attacks)": ci["asr"], "Utility (benign)": ci["utility"]}), "",
        "## ASR by scenario", "", *_table(agg["matrix"], d, "scenario", ci["matrix"]), "",
        "## ASR by attack class", "", *_table(agg["by_class"], d, "class", ci["by_class"]), "",
        "## Payload mutation families", "", "| mutation | attempts | success rate |", "|---|---|---|",
        *[f"| {m} | {v['n']} | {_pct(v['success_rate'])} |" for m, v in agg["mutations"].items()], "",
        "## Case studies", "",
    ]
    for c in agg["cases"]:
        lines += [f"### {c['class']}: `{c['scenario']}` (defense: {c['defense']}, mutation: {c['mutation']})", "",
                  "Payload:", "```", *[f"[{k}] {v}" for k, v in c["payloads"].items()], "```",
                  "Calls:", "```", *c["calls"], "```", f"Why it counts: {', '.join(c['reasons'])}", ""]
    acc = agg["judge_accuracy"]
    lines += ["## Totals", "",
              f"- Trials: {t['trials']} ({t['attack_trials']} attack, {t['benign_trials']} benign)",
              f"- Tokens: {t['tokens_in']} in / {t['tokens_out']} out, cost ${t['cost_usd']}",
              f"- Judge accuracy on hand-labeled set: {_pct(acc) if acc is not None else 'not run'}", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AgentArena Report</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--line:#e7e5e4;--asr:#c2410c;--util:#0f766e}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--line:#44403c;
--asr:#fb923c;--util:#2dd4bf}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}
main{max-width:960px;margin:auto}h1{margin:0 0 4px}.mode{color:var(--muted);margin-bottom:24px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:8px 0 24px;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right}
th:first-child,td:first-child{text-align:left}
pre{background:color-mix(in srgb,var(--fg) 6%,transparent);padding:10px;overflow-x:auto;font-size:13px}
.chart{position:relative;height:320px}
</style></head><body><main>
<h1>AgentArena</h1><div class="mode">Mode: <strong>__MODE__</strong> &middot; ASR lower is better,
utility higher is better</div>
<h2>Security vs utility by defense</h2><div class="chart"><canvas id="c"></canvas></div>
__TABLES__
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"
integrity="sha384-bs/nf9FbdNouRbMiFcrcZfLXYPKiPaGVGplVbv7dLGECccEXDW+S3zjqSKR5ZEaD" crossorigin="anonymous"></script>
<script>
const D=__DATA__;const css=getComputedStyle(document.documentElement);const v=n=>css.getPropertyValue(n).trim();
Chart.defaults.color=v('--muted');Chart.defaults.borderColor=v('--line');
new Chart(document.getElementById('c'),{type:'bar',data:{labels:D.defenses,datasets:[
{label:'ASR (attacks)',data:D.defenses.map(d=>D.asr[d]),backgroundColor:v('--asr')},
{label:'Utility (benign)',data:D.defenses.map(d=>D.utility[d]),backgroundColor:v('--util')}]},
options:{maintainAspectRatio:false,scales:{y:{min:0,max:1,ticks:{callback:x=>Math.round(x*100)+'%'}}}}});
</script></body></html>"""


def _html_table(rows: dict[str, dict[str, float | None]], defenses: list[str], first: str,
                ci: dict[str, dict[str, list[float] | None]]) -> str:
    head = "".join(f"<th>{html.escape(d)}</th>" for d in defenses)
    body = "".join(f"<tr><td>{html.escape(k)}</td>" + "".join(f"<td>{_cell(v[d], ci[k][d])}</td>" for d in defenses)
                   + "</tr>" for k, v in rows.items())
    return f'<div class="scroll"><table><tr><th>{first}</th>{head}</tr>{body}</table></div>'


def write_html(agg: dict, path: Path) -> None:
    d = agg["defenses"]
    t = agg["totals"]
    muts = "".join(f"<tr><td>{html.escape(m)}</td><td>{v['n']}</td><td>{_pct(v['success_rate'])}</td></tr>"
                   for m, v in agg["mutations"].items())
    cases = "".join(
        f"<h3>{html.escape(c['class'])}: {html.escape(c['scenario'])} ({html.escape(c['defense'])}, "
        f"{html.escape(c['mutation'])})</h3><pre>"
        + html.escape("\n".join([*(f"[{k}] {v}" for k, v in c["payloads"].items()), "", *c["calls"]]))
        + "</pre>" for c in agg["cases"])
    acc = agg["judge_accuracy"]
    ci = agg["ci"]
    tables = (
        f'<p class="mode">{CI_NOTE}</p>'
        + "<h2>ASR by scenario</h2>" + _html_table(agg["matrix"], d, "scenario", ci["matrix"])
        + "<h2>ASR by attack class</h2>" + _html_table(agg["by_class"], d, "class", ci["by_class"])
        + "<h2>Utility (benign)</h2>" + _html_table({"utility": agg["utility"]}, d, "metric",
                                                    {"utility": ci["utility"]})
        + '<h2>Payload mutation families</h2><div class="scroll"><table><tr><th>mutation</th><th>attempts</th>'
        + f"<th>success</th></tr>{muts}</table></div><h2>Case studies</h2>{cases}"
        + f"<h2>Totals</h2><p>{t['trials']} trials ({t['attack_trials']} attack, {t['benign_trials']} benign) "
        + f"&middot; {t['tokens_in']} in / {t['tokens_out']} out tokens &middot; ${t['cost_usd']} &middot; "
        + f"judge accuracy {_pct(acc) if acc is not None else 'not run'}</p>"
    )
    page = (HTML.replace("__MODE__", html.escape(agg["mode"])).replace("__TABLES__", tables)
            .replace("__DATA__", json.dumps({k: agg[k] for k in ("defenses", "asr", "utility")})))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
