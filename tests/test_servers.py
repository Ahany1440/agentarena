import json

from conftest import run

from agentarena.range.loader import get_scenario
from agentarena.range.servers import build_range, call_server


def test_read_file_stays_in_sandbox(tmp_path):
    servers, *_ = run(build_range(get_scenario("file_cleanup_overperm"), {}, tmp_path, "CANARY-x"))
    srv = servers["notes_files"]
    assert run(call_server(srv, "read_file", {"path": "../../etc/passwd"})) == "ERROR: outside sandbox"
    assert "Cleanup checklist" in run(call_server(srv, "read_file", {"path": "notes/cleanup.txt"}))


def test_send_email_writes_local_outbox(tmp_path):
    servers, _, _, state = run(build_range(get_scenario("benign_issue_triage"), {}, tmp_path, "CANARY-x"))
    run(call_server(servers["email"], "send_email", {"to": "dana@corp.test", "subject": "s", "body": "b"}))
    assert state.outbox == [{"to": "dana@corp.test", "subject": "s", "body": "b"}]
    assert json.loads((tmp_path / "outbox.json").read_text())[0]["to"] == "dana@corp.test"


def test_tool_description_payload_is_injected_only_in_live_spec(tmp_path):
    _, specs, clean, _ = run(build_range(get_scenario("poisoned_notes_tool"), {"desc": "EVIL"}, tmp_path, "C"))
    assert specs["list_files"].description.endswith("EVIL")
    assert "EVIL" not in clean["list_files"].description
