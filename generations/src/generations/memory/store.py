from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

DEFAULT_MEMORY: dict[str, Any] = {
    "current_criteria_version": 1,
    "criteria_history": [
        {
            "version": 1,
            "summary": "Advance the game, advance the platform, evolve the website honestly, and keep the workspace tidy.",
            "ship_rules": [
                "Validate before merge.",
                "One final commit per loop.",
                "Keep the active game inside games/active/.",
            ],
            "notes": ["Fresh human-authored scaffold for the major refactor."],
        }
    ],
    "heuristics": [
        "Evolve the game toward a stronger, more shippable concept and implementation.",
        "Evolve the platform when it improves autonomous game-development capability.",
        "Evolve the website to improve clarity, trust, and honest income potential.",
        "Keep the workspace coherent and tidy, and commit all intentional loop changes.",
    ],
    "heuristics_rolling_average": {
        "Evolve the game toward a stronger, more shippable concept and implementation.": 1.0,
        "Evolve the platform when it improves autonomous game-development capability.": 1.0,
        "Evolve the website to improve clarity, trust, and honest income potential.": 1.0,
        "Keep the workspace coherent and tidy, and commit all intentional loop changes.": 1.0,
    },
    "website_heuristics": [
        "Make the current loop legible to a human observer.",
        "Keep the journey page readable offline.",
    ],
    "website_heuristics_rolling_average": {
        "Make the current loop legible to a human observer.": 1.0,
        "Keep the journey page readable offline.": 1.0,
    },
    "monetization_heuristics": [
        "Keep monetization honest, minimal, and reversible.",
        "Do not optimize monetization ahead of product proof.",
    ],
    "monetization_heuristics_rolling_average": {
        "Keep monetization honest, minimal, and reversible.": 1.0,
        "Do not optimize monetization ahead of product proof.": 1.0,
    },
    "monetization_experiments": [
        {
            "timestamp": None,
            "name": "support_placeholder",
            "status": "active",
            "reason": "Bootstrap an honest support area while the game is still early.",
            "outcome": "unknown",
        }
    ],
    "active_game": {
        "root": "games/active",
        "name": "space_logistics",
        "status": "concept",
        "current_thesis": "Build a transport and logistics game with simulation depth and a plausible commercial trajectory.",
    },
    "pillar_state": {
        key: {"trajectory": "unclear", "confidence": 0.5} for key in ["game", "self", "website", "tidiness"]
    },
    "planning": {"current": None, "history": []},
    "current_loop_plan": None,
    "execution_history": {
        "recent_task_success_rate": 0.0,
        "recent_merge_success_rate": 0.0,
        "recent_validation_pass_rate": 0.0,
    },
    "outcomes": {
        "pass_count": 0,
        "fail_count": 0,
        "last_error": None,
        "last_successful_loop": None,
        "last_validation": None,
    },
    "evaluation_metrics": {
        "current": {key: 0.0 for key in ["creativity", "code_change", "review_quality", "game_progress", "observability", "balance"]},
        "rolling_average": {key: 0.0 for key in ["creativity", "code_change", "review_quality", "game_progress", "observability", "balance"]},
        "recent_history": [],
        "notes": [
            "Metrics are advisory, not authoritative.",
            "Planning records determine larger chunks of work.",
        ],
    },
}


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()
        self._ensure_snapshot()

    def _init_schema(self) -> None:
        with self._lock:
            self.connection.execute(
                "create table if not exists memory_snapshots (id integer primary key autoincrement, created_at text not null, payload text not null)"
            )
            self.connection.commit()

    def _ensure_snapshot(self) -> None:
        with self._lock:
            row = self.connection.execute("select payload from memory_snapshots order by id desc limit 1").fetchone()
        if row is None:
            self.replace(copy.deepcopy(DEFAULT_MEMORY), created_at="bootstrap")

    def latest(self) -> dict[str, Any]:
        with self._lock:
            row = self.connection.execute("select payload from memory_snapshots order by id desc limit 1").fetchone()
        if row is None:
            return copy.deepcopy(DEFAULT_MEMORY)
        return json.loads(row["payload"])

    def replace(self, payload: dict[str, Any], created_at: str = "update") -> None:
        with self._lock:
            self.connection.execute(
                "insert into memory_snapshots(created_at, payload) values(?, ?)",
                (created_at, json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def update_current_loop_plan(self, plan: dict[str, Any] | None) -> None:
        updated = self.latest()
        updated["current_loop_plan"] = plan
        self.replace(updated)

    def snapshot_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "select id, created_at, payload from memory_snapshots order by id desc"
            ).fetchall()
        return [dict(row) for row in rows]
