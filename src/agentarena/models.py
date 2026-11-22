"""Pydantic data models shared across AgentArena."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AttackClass = Literal[
    "indirect_injection", "tool_poisoning", "cross_server", "exfiltration",
    "goal_hijack", "over_permission", "benign",
]
InjectionKind = Literal["email_body", "issue_text", "web_page", "tool_description", "file"]
ServerName = Literal["email", "github_issues", "notes_files", "web_page"]


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class InjectionPoint(BaseModel):
    id: str
    kind: InjectionKind
    target: str  # "email:<id>" | "issue:<n>" | "page:<url>" | "tool:<name>" | "file:<path>"


class ForbiddenCall(BaseModel):
    """Forbidden if tool matches AND (args_not is None OR any args[k] != v)."""

    tool: str
    args_not: dict[str, str] | None = None

    def matches(self, call: ToolCall) -> bool:
        if call.name != self.tool:
            return False
        if self.args_not is None:
            return True
        return any(str(call.args.get(k)) != v for k, v in self.args_not.items())


class AttackGoal(BaseModel):
    description: str
    tool: str
    args: dict[str, str]  # may contain "$SECRET"


class Utility(BaseModel):
    must_call: list[str] = Field(default_factory=list)
    output_contains: list[str] = Field(default_factory=list)


class Policy(BaseModel):
    allowed_tools: list[str]


class Fixtures(BaseModel):
    emails: list[dict] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)
    pages: dict[str, str] = Field(default_factory=dict)
    files: dict[str, str] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str
    title: str
    attack_class: AttackClass
    task: str
    servers: list[ServerName]
    task_tools: list[ToolCall]
    injection_points: list[InjectionPoint] = Field(default_factory=list)
    goal: AttackGoal | None = None
    seed_payload: str | None = None
    forbidden: list[ForbiddenCall] = Field(default_factory=list)
    output_marker: str | None = None
    utility: Utility = Field(default_factory=Utility)
    policy: Policy
    fixtures: Fixtures = Field(default_factory=Fixtures)


class ToolSpec(BaseModel):
    server: str
    name: str
    description: str
    input_schema: dict
    sensitive: bool = False
    untrusted_output: bool = False
    sink_args: list[str] = Field(default_factory=list)


class CallRecord(BaseModel):
    call: ToolCall
    result: str
    blocked_by: str | None = None


class Transcript(BaseModel):
    calls: list[CallRecord] = Field(default_factory=list)
    final_output: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


class Attempt(BaseModel):
    id: str
    scenario: str
    defense: str
    index: int
    parent_id: str | None = None
    mutation: str
    payloads: dict[str, str] = Field(default_factory=dict)


class Verdict(BaseModel):
    success: bool
    method: Literal["rule", "llm"]
    reasons: list[str] = Field(default_factory=list)


class TrialResult(BaseModel):
    attempt: Attempt
    transcript: Transcript
    verdict: Verdict
    utility_ok: bool | None = None
    canary: str
    seed: int
    cost_usd: float = 0.0


class ArenaConfig(BaseModel):
    victim_model: str = "claude-haiku-5-5"
    attacker_model: str = "claude-sonnet-5-5"
    judge_model: str = "claude-haiku-5-5"
    attempts: int = 30
    concurrency: int = 4
    budget_tokens: int = 300_000
    db_path: str = "runs/arena.db"
    payloads_path: str = "runs/payloads.jsonl"
    report_dir: str = "report"
    seed: int = 1337
    defenses: list[str] = Field(
        default_factory=lambda: ["none", "scanner", "taint", "allowlist", "spotlight", "monitor", "all"]
    )
