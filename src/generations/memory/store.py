from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_MEMORY = {
    "current_criteria_version": 1,
    "criteria_history": [
        {
            "version": 1,
            "summary": "Improve autonomy, preserve safety, and keep website/journal observable.",
            "ship_rules": [
                "Only ship a game candidate after smoke validation passes repeatedly.",
                "Prefer small reversible changes with one commit per loop.",
                "Record all criteria and monetization changes in journal and memory.",
            ],
            "notes": [
                "Initial bootstrap criteria seeded from repository creation.",
            ],
        }
    ],
    "outcomes": {
        "pass_count": 0,
        "fail_count": 0,
        "last_error": None,
        "last_successful_loop": None,
        "last_validation": None,
    },
    "heuristics": [
        "Favor tiny, coherent edits over ambitious rewrites.",
        "Delay game scope growth until the website, journal, and memory remain healthy.",
    ],
    "website_heuristics": [
        "Keep the journey page readable offline.",
        "Only add monetization experiments that are honest and reversible.",
    ],
    "monetization_heuristics": [
        "Start with a support placeholder and disclosure.",
        "Track experiments explicitly before optimizing them.",
    ],
    "monetization_experiments": [
        {
            "timestamp": None,
            "name": "support_placeholder",
            "status": "active",
            "reason": "Bootstrap an honest support area without committing to a final strategy.",
            "outcome": "unknown",
        }
    ],
    "tool_routing": {
        "execution_surface": "OpenCode CLI adapter",
        "model_provider": "Ollama local daemon adapter",
    },
}


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()
        self._ensure_snapshot()

    def _init_schema(self) -> None:
        self.connection.execute(
            "create table if not exists memory_snapshots (id integer primary key autoincrement, created_at text not null, payload text not null)"
        )
        self.connection.commit()

    def _ensure_snapshot(self) -> None:
        row = self.connection.execute(
            "select payload from memory_snapshots order by id desc limit 1"
        ).fetchone()
        if row is None:
            self.replace(DEFAULT_MEMORY, created_at="bootstrap")

    def latest(self) -> dict[str, Any]:
        row = self.connection.execute(
            "select payload from memory_snapshots order by id desc limit 1"
        ).fetchone()
        if row is None:
            return dict(DEFAULT_MEMORY)
        return json.loads(row["payload"])

    def replace(self, payload: dict[str, Any], created_at: str) -> None:
        self.connection.execute(
            "insert into memory_snapshots(created_at, payload) values(?, ?)",
            (created_at, json.dumps(payload, sort_keys=True)),
        )
        self.connection.commit()

    def snapshot_rows(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "select id, created_at, payload from memory_snapshots order by id desc"
        ).fetchall()
        return [dict(row) for row in rows]
