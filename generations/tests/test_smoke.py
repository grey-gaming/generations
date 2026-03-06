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


@pytest.mark.slow
def test_run_writes_planning_and_journal(tmp_path: Path) -> None:
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

    journal = (tmp_path / "state" / "journal.jsonl").read_text(encoding="utf-8")
    runtime = json.loads((tmp_path / "state" / "runtime.json").read_text(encoding="utf-8"))
    planning = list((tmp_path / "state" / "planning").glob("planning-*.json"))
    current_loop_plan = json.loads((tmp_path / "state" / "current_loop_plan.json").read_text(encoding="utf-8"))
    assert '"entry_type": "planning_phase"' in journal
    assert runtime["loop_count"] == 1
    assert planning
    assert current_loop_plan["theme"]
