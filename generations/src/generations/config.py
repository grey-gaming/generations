from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

DEFAULT_MODEL = "qwen3.5:397b-cloud"
DEFAULT_PROVIDER = "ollama_cloud"


@dataclass(slots=True)
class AppConfig:
    root: Path
    generations_dir: Path
    games_dir: Path
    active_game_dir: Path
    sample_game_dir: Path
    state_dir: Path
    planning_dir: Path
    runs_dir: Path
    opencode_state_dir: Path
    journal_path: Path
    memory_path: Path
    runtime_path: Path
    current_loop_plan_path: Path
    pause_flag: Path
    web_export_dir: Path
    max_rest_seconds: int
    test_mode: bool
    debug: bool
    disable_web: bool
    opencode_agent: str
    operational_max_loops: int | None
    operational_loop_timeout_seconds: int | None
    parallel_tasks: int

    @classmethod
    def from_root(cls, root: Path, debug: bool | None = None) -> "AppConfig":
        state_dir = root / "state"
        planning_dir = state_dir / "planning"
        runs_dir = state_dir / "runs"
        opencode_state_dir = state_dir / "opencode"
        for item in (state_dir, planning_dir, runs_dir, opencode_state_dir):
            item.mkdir(parents=True, exist_ok=True)
        env_debug = os.getenv("GENERATIONS_DEBUG", "0") == "1"
        return cls(
            root=root,
            generations_dir=root / "generations",
            games_dir=root / "games",
            active_game_dir=root / "games" / "active",
            sample_game_dir=root / "games" / "hello_game",
            state_dir=state_dir,
            planning_dir=planning_dir,
            runs_dir=runs_dir,
            opencode_state_dir=opencode_state_dir,
            journal_path=state_dir / "journal.jsonl",
            memory_path=state_dir / "memory.sqlite3",
            runtime_path=state_dir / "runtime.json",
            current_loop_plan_path=state_dir / "current_loop_plan.json",
            pause_flag=state_dir / "pause.flag",
            web_export_dir=root / "site",
            max_rest_seconds=int(os.getenv("GENERATIONS_MAX_REST_SECONDS", "5")),
            test_mode=os.getenv("GENERATIONS_TEST_MODE", "0") == "1",
            debug=env_debug if debug is None else debug,
            disable_web=os.getenv("GENERATIONS_DISABLE_WEB", "0") == "1",
            opencode_agent=os.getenv("GENERATIONS_OPENCODE_AGENT", "build"),
            operational_max_loops=_optional_int(os.getenv("GENERATIONS_MAX_LOOPS")),
            operational_loop_timeout_seconds=_optional_int(os.getenv("GENERATIONS_LOOP_TIMEOUT_SECONDS")),
            parallel_tasks=int(os.getenv("GENERATIONS_PARALLEL_TASKS", "3")),
        )


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value)
