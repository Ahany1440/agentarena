from conftest import run

from agentarena.range.loader import get_scenario
from agentarena.report.report import aggregate
from agentarena.runner.runner import run_matrix
from agentarena.runner.store import Store


def test_injection_succeeds_undefended_and_all_defenses_reduce_asr(cfg):
    cfg.attempts = 12
    scns = [get_scenario("inbox_summary_exfil"), get_scenario("benign_inbox_summary")]
    run(run_matrix(scns, ["none", "all"], cfg, "mock", "e2e"))
    agg = aggregate(Store(cfg.db_path).results("e2e"))
    assert agg["asr"]["none"] > 0
    assert agg["asr"]["all"] < agg["asr"]["none"]
    assert agg["utility"]["none"] == 1.0
