from __future__ import annotations

from pathlib import Path
import json
from typing import Any


class PlanningStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, planning_loop: int, payload: dict[str, Any]) -> Path:
        out = self.path / f"planning-{planning_loop:04d}.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return out
