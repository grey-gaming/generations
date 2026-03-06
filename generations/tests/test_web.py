from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.memory.store import MemoryStore
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
    assert "Current Loop Plan" in html
    assert "Create the first plan" in html
