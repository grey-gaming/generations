from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.web.presentation import visible_journal_entries
from generations.web.exporter import export_site


def test_export_site_renders_vision_and_block_sections(tmp_path: Path) -> None:
    root = tmp_path
    (root / "state").mkdir()
    config = AppConfig.from_root(root)
    memory = MemoryStore(config.memory_path)
    payload = memory.latest()
    payload["long_term_vision"]["current_version"] = 1
    payload["long_term_vision"]["last_refined_loop"] = 0
    payload["long_term_vision"]["current"] = {
        "index_summary": "Long-term direction for the three pillars.",
        "pillars": {
            "self": {"summary": "Build the autonomous platform.", "good_end_state": "A reliable autonomous studio."},
            "game": {"summary": "Build the transport game.", "good_end_state": "A playable prototype."},
            "monetization_platform": {"summary": "Build honest support surfaces.", "good_end_state": "A transparent public support layer."},
        },
    }
    payload["block_planning"]["current"] = {
        "block_id": 1,
        "primary_pillar": "self",
        "execution_range": [2, 10],
        "why_this_pillar_now": "The platform needs structure first.",
        "target_outcomes": ["Clarify planning"],
        "allowed_support_work": ["Website visibility"],
        "explicit_non_goals": ["Broad game implementation"],
        "review_focus": ["Does the platform get clearer?"],
    }
    memory.replace(payload)
    memory.update_current_loop_plan({
        "loop_counter": 1,
        "theme": "Block 1 planning",
        "goal": "Plan the first self block",
        "primary_pillar": "self",
        "block_id": 1,
        "tasks": [],
        "integration_status": "committed",
        "validation_status": "passed",
        "updated_at": "2026-03-06T00:00:00Z",
    })
    export_site(root, config, [], memory.latest(), out_dir=root / "site")
    html = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert "Long-Term Vision" in html
    assert "Current Block" in html
    assert "Metrics As Signals" in html


def test_export_site_hides_rest_entries_from_diary(tmp_path: Path) -> None:
    root = tmp_path
    config = AppConfig.from_root(root)
    journal = JournalStore(config.journal_path)
    journal.append({
        "timestamp": "2026-03-06T00:00:00Z",
        "entry_type": "vision",
        "loop_counter": 0,
        "long_term_vision": {"index_summary": "Founding vision."},
    })
    journal.append({
        "timestamp": "2026-03-06T00:00:01Z",
        "entry_type": "rest_cycle",
        "loop_counter": 2,
        "reason": "Planner requested neutral rest.",
    })
    export_site(root, config, journal.read_all(), MemoryStore(config.memory_path).latest(), out_dir=root / "site")
    html = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert "Founding vision." in html
    assert "Planner requested neutral rest." not in html


def test_visible_journal_entries_filters_rest_and_rest_cycle() -> None:
    entries = [
        {"entry_type": "vision", "loop_counter": 0},
        {"entry_type": "rest", "loop_counter": 0},
        {"entry_type": "rest_cycle", "loop_counter": 1},
        {"entry_type": "loop", "loop_counter": 2},
    ]
    filtered = visible_journal_entries(entries)
    assert [entry["entry_type"] for entry in filtered] == ["vision", "loop"]
