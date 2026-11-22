from agentarena.range.loader import load_scenarios
from agentarena.range.servers import PLACEHOLDER, SERVER_TOOLS


def test_all_scenarios_load_with_unique_ids():
    scns = load_scenarios()
    assert len(scns) == 11
    assert len({s.id for s in scns}) == len(scns)
    assert {s.attack_class for s in scns} >= {"indirect_injection", "tool_poisoning", "cross_server",
                                               "exfiltration", "goal_hijack", "over_permission", "benign"}


def test_placeholders_map_to_injection_points_and_tools_exist():
    for s in load_scenarios():
        points = {p.id for p in s.injection_points}
        assert set(PLACEHOLDER.findall(s.fixtures.model_dump_json())) <= points, s.id
        tools = {t for srv in s.servers for t in SERVER_TOOLS[srv]}
        assert {c.name for c in s.task_tools} <= tools, s.id
        assert set(s.policy.allowed_tools) <= tools, s.id
        if s.attack_class != "benign":
            assert s.goal and points, s.id
