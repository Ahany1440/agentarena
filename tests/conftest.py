import asyncio
from pathlib import Path

import pytest

from agentarena.models import ArenaConfig


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def cfg(tmp_path: Path) -> ArenaConfig:
    return ArenaConfig(attempts=6, concurrency=4, db_path=str(tmp_path / "a.db"),
                       payloads_path=str(tmp_path / "p.jsonl"), report_dir=str(tmp_path / "report"))
