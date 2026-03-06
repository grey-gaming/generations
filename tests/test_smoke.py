from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_single_safe_loop_writes_journal_and_memory(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["GENERATIONS_TEST_MODE"] = "1"
    env["GENERATIONS_LOOP_TIMEOUT_SECONDS"] = "30"

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)

    for relative in ["src", "games", "tests", "pyproject.toml", "README.md"]:
        source = repo_root / relative
        target = tmp_path / relative
        if source.is_dir():
            subprocess.run(["cp", "-R", str(source), str(target)], check=True)
        else:
            subprocess.run(["cp", str(source), str(target)], check=True)

    result = subprocess.run(
        [sys.executable, "-m", "generations.cli", "run", "--seed", "smoke seed"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    journal_path = tmp_path / "state" / "journal.jsonl"
    memory_path = tmp_path / "state" / "memory.sqlite3"
    site_index = tmp_path / "site" / "index.html"

    assert journal_path.exists()
    assert memory_path.exists()
    assert site_index.exists()

    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    first_entry = json.loads(lines[0])
    assert first_entry["model_provider"]["selected_default_model"] == "qwen3.5:397b-cloud"


def test_ship_rules_criteria_file_exists(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    criteria_path = repo_root / "criteria.json"
    assert criteria_path.exists(), "criteria.json must exist for ship rule enforcement"

    criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
    assert "ship_rules" in criteria
    assert any(rule["id"] == "DATA_SCHEMA_REQUIRED" for rule in criteria["ship_rules"])


def test_loop_timeout_config_exists() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    import subprocess
    import os

    env = dict(**os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["GENERATIONS_TEST_MODE"] = "1"
    env["GENERATIONS_LOOP_TIMEOUT_SECONDS"] = "10"

    result = subprocess.run(
        [sys.executable, "-c", "from generations.config import AppConfig; from pathlib import Path; c = AppConfig.from_root(Path('.')); print(c.operational_loop_timeout_seconds)"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "10"


def test_economy_balance_criteria_exists(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    criteria_path = repo_root / "criteria.json"
    criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
    assert "ship_rules" in criteria
    assert any(rule["id"] == "ECONOMY_BALANCE_REQUIRED" for rule in criteria["ship_rules"])
