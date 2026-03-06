from __future__ import annotations

import json
import sqlite3
import threading
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
        "Favor coherent, reviewable steps inside a larger strategic arc.",
        "Delay game scope growth until the website, journal, and memory remain healthy.",
        "Think in larger arcs even when executing in small steps.",
        "Improve the platform when it increases autonomous game-development capability.",
        "Prefer steps that unlock future game-building capability, not just local housekeeping.",
    ],
    "heuristics_rolling_average": {
        "Favor coherent, reviewable steps inside a larger strategic arc.": 1.0,
        "Delay game scope growth until the website, journal, and memory remain healthy.": 1.0,
        "Think in larger arcs even when executing in small steps.": 1.0,
        "Improve the platform when it increases autonomous game-development capability.": 1.0,
        "Prefer steps that unlock future game-building capability, not just local housekeeping.": 1.0,
    },
    "heuristics_recent_history": [],
    "strategic_intent": {
        "current_direction": "Grow from autonomous software bootstrap into a system capable of designing and building a commercially plausible game.",
        "current_game_thesis": "No fixed thesis yet. Explore systems that could support a strong game premise.",
        "next_big_questions": [
            "What game concept is compelling enough to justify sustained development?",
            "What capabilities must the autonomous platform gain before building a serious prototype?",
            "What simulation, economy, logistics, UI, and content systems would make the eventual game distinctive?",
        ],
    },
    "website_heuristics": [
        "Keep the journey page readable offline.",
        "Only add monetization experiments that are honest and reversible.",
    ],
    "website_heuristics_rolling_average": {
        "Keep the journey page readable offline.": 1.0,
        "Only add monetization experiments that are honest and reversible.": 1.0,
    },
    "monetization_heuristics": [
        "Start with a support placeholder and disclosure.",
        "Track experiments explicitly before optimizing them.",
    ],
    "monetization_heuristics_rolling_average": {
        "Start with a support placeholder and disclosure.": 1.0,
        "Track experiments explicitly before optimizing them.": 1.0,
    },
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
    "evaluation_metrics": {
        "current": {
            "creativity": 0.0,
            "code_change": 0.0,
            "review_quality": 0.0,
            "game_progress": 0.0,
            "observability": 0.0,
            "balance": 0.0,
        },
        "rolling_average": {
            "creativity": 0.0,
            "code_change": 0.0,
            "review_quality": 0.0,
            "game_progress": 0.0,
            "observability": 0.0,
            "balance": 0.0,
        },
        "recent_history": [],
        "notes": [
            "Metrics guide balancing, but the model still chooses the next step.",
            "Low code_change or game_progress should bias future loops toward meaningful repo edits.",
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
            row = self.connection.execute(
                "select payload from memory_snapshots order by id desc limit 1"
            ).fetchone()
        if row is None:
            self.replace(DEFAULT_MEMORY, created_at="bootstrap")

    def latest(self) -> dict[str, Any]:
        with self._lock:
            row = self.connection.execute(
                "select payload from memory_snapshots order by id desc limit 1"
            ).fetchone()
        if row is None:
            return dict(DEFAULT_MEMORY)
        return json.loads(row["payload"])

    def replace(self, payload: dict[str, Any], created_at: str) -> None:
        with self._lock:
            self.connection.execute(
                "insert into memory_snapshots(created_at, payload) values(?, ?)",
                (created_at, json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def snapshot_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "select id, created_at, payload from memory_snapshots order by id desc"
            ).fetchall()
        return [dict(row) for row in rows]
