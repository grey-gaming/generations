from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

DEFAULT_MODEL = "qwen3.5:397b-cloud"
DEFAULT_PROVIDER = "ollama_cloud"


@dataclass(slots=True)
class AppConfig:
    root: Path
    state_dir: Path
    journal_path: Path
    memory_path: Path
    status_path: Path
    pause_flag: Path
    runtime_path: Path
    web_export_dir: Path
    games_dir: Path
    opencode_state_dir: Path
    opencode_agent: str
    max_rest_seconds: int
    debug: bool
    disable_web: bool
    test_mode: bool
    operational_max_loops: int | None
    operational_loop_timeout_seconds: int | None

    @classmethod
    def from_root(cls, root: Path) -> "AppConfig":
        state_dir = root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            root=root,
            state_dir=state_dir,
            journal_path=state_dir / "journal.jsonl",
            memory_path=state_dir / "memory.sqlite3",
            status_path=state_dir / "status.json",
            pause_flag=state_dir / "pause.flag",
            runtime_path=state_dir / "runtime.json",
            web_export_dir=root / "site",
            games_dir=root / "games",
            opencode_state_dir=state_dir / "opencode",
            opencode_agent=os.getenv("GENERATIONS_OPENCODE_AGENT", "build"),
            max_rest_seconds=int(os.getenv("GENERATIONS_MAX_REST_SECONDS", "5")),
            debug=os.getenv("GENERATIONS_DEBUG", "0") == "1",
            disable_web=os.getenv("GENERATIONS_DISABLE_WEB", "0") == "1",
            test_mode=os.getenv("GENERATIONS_TEST_MODE", "0") == "1",
            operational_max_loops=_optional_int(os.getenv("GENERATIONS_MAX_LOOPS")),
            operational_loop_timeout_seconds=_optional_int(os.getenv("GENERATIONS_LOOP_TIMEOUT_SECONDS", "300")),
        )


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
