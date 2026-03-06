from __future__ import annotations

from pathlib import Path

from generations.journal.store import JournalStore
from generations.runner import Runner, init_repo_if_needed


def test_journal_is_append_only(tmp_path: Path) -> None:
    journal = JournalStore(tmp_path / "journal.jsonl")
    journal.append({"loop": 1, "message": "first"})
    journal.append({"loop": 2, "message": "second"})

    raw = (tmp_path / "journal.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entries = journal.read_all()

    assert len(raw) == 2
    assert entries[0]["message"] == "first"
    assert entries[1]["message"] == "second"


def test_planning_phase_records_current_plan(tmp_path: Path) -> None:
    init_repo_if_needed(tmp_path)
    runner = Runner(tmp_path, "seed")

    for loop in range(1, 11):
        runner.journal.append(
            {
                "loop_counter": loop,
                "timestamp": f"2026-03-06T00:00:{loop:02d}+00:00",
                "next_step": {"description": f"loop {loop}", "rationale": "test"},
            }
        )
    runner.runtime.loop_count = 10

    def fake_plan_next_arc(seed: str, loop_count: int, recent_entries: list[dict[str, object]], memory: dict[str, object]):
        return (
            {
                "planning_loop": loop_count,
                "retrospective_summary": "Ten-loop retrospective.",
                "wins": ["kept running"],
                "mistakes": ["some weak loops"],
                "repeated_patterns": ["docs-heavy moves"],
                "next_chunk_theme": "Build stronger game chunks",
                "next_chunk_goals": ["ship more meaningful repo edits"],
                "next_chunk_focus": ["game pipeline"],
                "risks": ["website drift"],
                "website_plan": "Reflect the next chunk clearly.",
                "monetization_plan": "Hold steady.",
                "rationale": "Use the next chunk to move from reflection to execution.",
            },
            {
                "provider": "test",
                "model": "stub",
                "stubbed": True,
                "planning_call": True,
                "fallback": None,
            },
        )

    runner.model.plan_next_arc = fake_plan_next_arc  # type: ignore[method-assign]
    memory = runner.memory.latest()
    updated = runner._maybe_run_planning_phase(11, memory, "seedhash")

    assert updated["planning"]["current"]["planning_loop"] == 10
    assert updated["planning"]["current"]["next_chunk_theme"] == "Build stronger game chunks"
    assert runner.journal.read_all()[-1]["entry_type"] == "planning_phase"
