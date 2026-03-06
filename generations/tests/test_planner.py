from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.models import PlanningRecord
from generations.planner import Planner


class StubModel:
    def plan_checkpoint(self, seed, runtime_loop_count, memory, recent_entries):
        record = PlanningRecord(
            planning_loop=runtime_loop_count,
            generated_at="2026-03-06T00:00:00Z",
            good_end_state={
                "game": "g",
                "self": "s",
                "website": "w",
                "tidiness": "t",
            },
            pillar_assessment={
                "game": "strong direction",
                "self": {"trajectory": "on_track", "confidence": "0.8"},
            },
            horizon_10={"theme": "theme"},
            horizon_100={"theme": "h100"},
            horizon_250={"vision": "h250"},
            retro={"wins": []},
            planner_rationale="rationale",
        )
        return record, {"provider": "stub"}


def test_planner_normalizes_partial_pillar_assessment(tmp_path: Path) -> None:
    config = AppConfig.from_root(tmp_path)
    journal = JournalStore(config.journal_path)
    memory = MemoryStore(config.memory_path)
    planner = Planner(config, StubModel(), journal, memory)

    record = planner.ensure_checkpoint("seed", 0)

    assert record.pillar_assessment["game"]["trajectory"] == "unclear"
    assert record.pillar_assessment["game"]["current_state"] == "strong direction"
    assert record.pillar_assessment["self"]["trajectory"] == "on_track"
    assert record.pillar_assessment["website"]["trajectory"] == "unclear"
