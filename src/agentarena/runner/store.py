"""SQLite trial store: one row per trial, keyed so a crashed run can resume."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from agentarena.models import TrialResult

SCHEMA = """CREATE TABLE IF NOT EXISTS trials (
  key TEXT PRIMARY KEY, run_id TEXT, scenario TEXT, defense TEXT, idx INTEGER, success INTEGER,
  utility_ok INTEGER, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL, result_json TEXT, created REAL)"""


def trial_key(run_id: str, scenario: str, defense: str, idx: int) -> str:
    return f"{run_id}:{scenario}:{defense}:{idx}"


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)

    def has(self, key: str) -> bool:
        return self.db.execute("SELECT 1 FROM trials WHERE key=?", (key,)).fetchone() is not None

    def save(self, run_id: str, r: TrialResult) -> None:
        a, t = r.attempt, r.transcript
        self.db.execute(
            "INSERT OR REPLACE INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (trial_key(run_id, a.scenario, a.defense, a.index), run_id, a.scenario, a.defense, a.index,
             int(r.verdict.success), None if r.utility_ok is None else int(r.utility_ok),
             t.tokens_in, t.tokens_out, r.cost_usd, r.model_dump_json(), time.time()),
        )
        self.db.commit()

    def results(self, run_id: str) -> list[TrialResult]:
        rows = self.db.execute("SELECT result_json FROM trials WHERE run_id=? ORDER BY scenario, defense, idx",
                               (run_id,))
        return [TrialResult.model_validate_json(r[0]) for r in rows]

    def runs(self) -> list[str]:
        rows = self.db.execute("SELECT run_id FROM trials GROUP BY run_id ORDER BY MAX(created) DESC")
        return [r[0] for r in rows]
