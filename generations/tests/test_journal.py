from __future__ import annotations

import json
from pathlib import Path

from generations.journal.store import JournalStore


def test_journal_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    store = JournalStore(path)
    store.append({"entry_type": "loop", "loop_counter": 0})
    store.append({"entry_type": "rest", "loop_counter": 0})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["entry_type"] == "loop"
    assert json.loads(lines[1])["entry_type"] == "rest"
