import pytest
from conftest import run

from agentarena.range.loader import get_scenario, load_scenarios
from agentarena.report.report import aggregate, write_html, write_markdown
from agentarena.runner import runner
from agentarena.runner.runner import run_matrix
from agentarena.runner.store import Store


def test_small_matrix_completes_and_reports(cfg, tmp_path):
    scns = [get_scenario("inbox_summary_exfil"), get_scenario("benign_inbox_summary")]
    assert run(run_matrix(scns, ["none", "all"], cfg, "mock", "r1"))
    results = Store(cfg.db_path).results("r1")
    assert len(results) == 2 * 2 * cfg.attempts
    agg = aggregate(results)
    write_markdown(agg, tmp_path / "report" / "report.md")
    write_html(agg, tmp_path / "report" / "index.html")
    assert "SIMULATED" in (tmp_path / "report" / "report.md").read_text(encoding="utf-8")


def test_resume_after_crash_has_no_duplicates(cfg, monkeypatch):
    real, calls = runner.run_trial, {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("simulated crash")
        return await real(*a, **k)

    cfg.concurrency = 1
    scns = [get_scenario("inbox_summary_exfil")]
    monkeypatch.setattr(runner, "run_trial", flaky)
    with pytest.raises(RuntimeError):
        run(run_matrix(scns, ["none"], cfg, "mock", "r2"))
    assert len(Store(cfg.db_path).results("r2")) == 3
    monkeypatch.setattr(runner, "run_trial", real)
    run(run_matrix(scns, ["none"], cfg, "mock", "r2"))
    idx = [r.attempt.index for r in Store(cfg.db_path).results("r2")]
    assert idx == list(range(cfg.attempts))


def test_full_demo_matrix_shape(cfg):
    cfg.attempts = 2
    scns = load_scenarios()
    run(run_matrix(scns, cfg.defenses, cfg, "mock", "r3"))
    assert len(Store(cfg.db_path).results("r3")) == len(scns) * len(cfg.defenses) * 2
