from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from generations.validation.state_validator import validate_loop_state

DEFAULT_MEMORY: dict[str, Any] = {
    "current_criteria_version": 1,
    "criteria_history": [
        {
            "version": 1,
            "summary": "Use long-term vision, 10-loop blocks, retrospectives, and honest metrics-as-signals.",
            "ship_rules": [
                "Validate before merge.",
                "One final commit per loop.",
                "Use block plans and retrospectives rather than ad-hoc direction changes.",
            ],
            "notes": ["Fresh scaffold for the block-driven refactor."],
        }
    ],
    "heuristics": [
        "Advance the current block coherently.",
        "Let metrics inform the next move without dictating it.",
        "Keep the workspace and public story legible.",
    ],
    "active_game": {
        "root": "games/active",
        "name": "space_logistics",
        "status": "visioning",
        "current_thesis": "Build a transport and logistics game with simulation depth and a plausible commercial trajectory.",
    },
    "pillars": {
        "self": {
            "summary": "The autonomous platform, its website, memory, validation, and operator visibility.",
            "trajectory": "unclear",
            "confidence": 0.5,
            "current_state": "Loop 0 vision has not been written yet.",
            "biggest_risk": "Platform work may become reactive instead of strategic.",
        },
        "game": {
            "summary": "The active game concept, implementation, tests, and design artifacts.",
            "trajectory": "unclear",
            "confidence": 0.5,
            "current_state": "The active game has only a seed thesis.",
            "biggest_risk": "Game work may begin before the platform can support it coherently.",
        },
        "monetization_platform": {
            "summary": "The honest commercial, support, and audience-building surfaces around the project.",
            "trajectory": "unclear",
            "confidence": 0.5,
            "current_state": "Only a support placeholder exists.",
            "biggest_risk": "Monetization could get ahead of product proof.",
        },
    },
    "long_term_vision": {
        "current_version": 0,
        "last_refined_loop": None,
        "current": None,
        "history": [],
    },
    "block_planning": {
        "current": None,
        "history": [],
    },
    "retrospectives": {
        "latest": None,
        "history": [],
    },
    "current_loop_plan": None,
    "execution_history": {
        "recent_task_success_rate": 0.0,
        "recent_merge_success_rate": 0.0,
        "recent_validation_pass_rate": 0.0,
    },
    "outcomes": {
        "pass_count": 0,
        "fail_count": 0,
        "rest_count": 0,
        "last_error": None,
        "last_successful_loop": None,
        "last_validation": None,
    },
    "evaluation_metrics": {
        "current": {key: 0.0 for key in ["creativity", "code_change", "review_quality", "game_progress", "observability", "balance"]},
        "rolling_average": {key: 0.0 for key in ["creativity", "code_change", "review_quality", "game_progress", "observability", "balance"]},
        "recent_history": [],
        "notes": [
            "Metrics are signals, not verdicts.",
            "Block plans and retrospectives carry the main strategic weight.",
        ],
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
}


class MemoryStore:
    def __init__(self, path: Path, schema_path: Path | None = None) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()
        self._schema_path = schema_path
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
            self._persist(copy.deepcopy(DEFAULT_MEMORY), created_at="bootstrap")

    def latest(self) -> dict[str, Any]:
        with self._lock:
            row = self.connection.execute("select payload from memory_snapshots order by id desc limit 1").fetchone()
        if row is None:
            return copy.deepcopy(DEFAULT_MEMORY)
        return json.loads(row["payload"])

    def _persist(self, payload: dict[str, Any], created_at: str) -> None:
        with self._lock:
            self.connection.execute(
                "insert into memory_snapshots(created_at, payload) values(?, ?)",
                (created_at, json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def write(self, payload: dict[str, Any], created_at: str = "update") -> None:
        """Write state to memory store with validation.
        
        Raises:
            ValueError: If state fails validation
        """
        if self._schema_path is not None:
            is_valid, errors = validate_loop_state(payload, self._schema_path)
            if not is_valid:
                error_msg = "; ".join(errors)
                raise ValueError(f"Memory state validation failed: {error_msg}")
        self._persist(payload, created_at)

    def update_current_loop_plan(self, plan: dict[str, Any] | None) -> None:
        updated = self.latest()
        updated["current_loop_plan"] = plan
        self._persist(updated, created_at="update")

    def snapshot_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "select id, created_at, payload from memory_snapshots order by id desc"
            ).fetchall()
        return [dict(row) for row in rows]
