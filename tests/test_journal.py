from __future__ import annotations

from pathlib import Path

from generations.journal.store import JournalStore


def test_journal_is_append_only(tmp_path: Path) -> None:
    journal = JournalStore(tmp_path / "journal.jsonl")
    journal.append({"loop": 1, "message": "first"})
    journal.append({"loop": 2, "message": "second"})

    raw = (tmp_path / "journal.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entries = journal.read_all()

    assert len(raw) == 2
    assert entries[0]["message"] == "first"
    assert entries[1]["message"] == "second"
