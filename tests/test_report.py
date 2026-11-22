from agentarena.report.report import _ci


def test_wilson_interval():
    assert _ci([]) is None
    assert _ci([True] * 5 + [False] * 5) == [0.237, 0.763]
    r = _ci([False] * 30)
    assert r is not None
    lo, hi = r
    assert lo == 0.0 and 0 < hi < 0.15  # 0/30 is not "proven 0%"
