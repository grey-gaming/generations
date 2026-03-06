from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.web.presentation import visible_journal_entries
from generations.web.exporter import export_site


def test_export_site_renders_current_plan(tmp_path: Path) -> None:
    root = tmp_path
    (root / "state").mkdir()
    config = AppConfig.from_root(root)
    memory = MemoryStore(config.memory_path)
    memory.update_current_loop_plan({
        "loop_counter": 0,
        "theme": "Bootstrap",
        "goal": "Create the first plan",
        "tasks": [{"task_id": "A", "scope": "platform", "objective": "Write plan", "status": "planned"}],
        "integration_status": "pending",
        "validation_status": "pending",
        "updated_at": "2026-03-06T00:00:00Z",
    })
    export_site(root, config, [], memory.latest(), out_dir=root / "site")
    html = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert "Current Loop" in html
    assert "Create the first plan" in html
    assert "Recent Metrics" in html


def test_export_site_hides_rest_entries_from_diary(tmp_path: Path) -> None:
    root = tmp_path
    config = AppConfig.from_root(root)
    journal = JournalStore(config.journal_path)
    journal.append({
        "timestamp": "2026-03-06T00:00:00Z",
        "entry_type": "planning_phase",
        "loop_counter": 0,
        "planning": {"horizon_10": {"theme": "Bootstrap executable motion"}},
    })
    journal.append({
        "timestamp": "2026-03-06T00:00:01Z",
        "entry_type": "rest",
        "loop_counter": 0,
        "reason": "Continue with another bounded step after a short rest.",
    })
    export_site(root, config, journal.read_all(), MemoryStore(config.memory_path).latest(), out_dir=root / "site")
    html = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert "Planning checkpoint" in html
    assert "Continue with another bounded step after a short rest." not in html


def test_visible_journal_entries_filters_rest() -> None:
    entries = [
        {"entry_type": "planning_phase", "loop_counter": 0},
        {"entry_type": "rest", "loop_counter": 0},
        {"entry_type": "loop", "loop_counter": 1},
    ]
    filtered = visible_journal_entries(entries)
    assert [entry["entry_type"] for entry in filtered] == ["planning_phase", "loop"]
