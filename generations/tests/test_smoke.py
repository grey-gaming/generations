from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT_ITEMS = [
    ".gitignore",
    "criteria.json",
    "pyproject.toml",
    "README.md",
    "games",
    "generations",
]


def _run_once(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path / "generations" / "src") + os.pathsep + str(tmp_path)
    env["GENERATIONS_TEST_MODE"] = "1"
    env["GENERATIONS_DISABLE_WEB"] = "1"
    subprocess.run(
        [sys.executable, "-m", "generations.cli", "run", "--seed", "bootstrap a transport game", "--parallel-tasks", "2"],
        cwd=tmp_path,
        env=env,
        check=True,
    )


@pytest.mark.slow
def test_run_writes_vision_then_initial_block_plan(tmp_path: Path) -> None:
    for item in ROOT_ITEMS:
        src = Path(item)
        dst = tmp_path / item
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Generations Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=tmp_path, check=True, capture_output=True)

    _run_once(tmp_path)
    runtime = json.loads((tmp_path / "state" / "runtime.json").read_text(encoding="utf-8"))
    journal = (tmp_path / "state" / "journal.jsonl").read_text(encoding="utf-8")
    vision = json.loads((tmp_path / "state" / "current_long_term_vision.json").read_text(encoding="utf-8"))
    self_vision = (tmp_path / "generations" / "vision" / "vision_v001_self.md").read_text(encoding="utf-8")
    seed_brief = (tmp_path / "games" / "active" / "design" / "seed_brief.md").read_text(encoding="utf-8")
    assert runtime["loop_count"] == 1
    assert '"entry_type": "vision"' in journal
    assert vision["version"] == 1
    assert len(self_vision.split()) >= 500
    assert "# Seed Brief" in seed_brief
    assert "Seed prompt:" in seed_brief

    _run_once(tmp_path)
    runtime = json.loads((tmp_path / "state" / "runtime.json").read_text(encoding="utf-8"))
    block_plan = json.loads((tmp_path / "state" / "current_block_plan.json").read_text(encoding="utf-8"))
    block_doc = (tmp_path / "generations" / "planning_docs" / "block_001_plan.md").read_text(encoding="utf-8")
    assert runtime["loop_count"] == 2
    assert block_plan["primary_pillar"] == "self"
    assert "Block 1 Plan" in block_doc
