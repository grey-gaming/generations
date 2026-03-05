from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


@dataclass(slots=True)
class RuntimeState:
    loop_count: int
    last_commit: str | None
    last_validation: dict[str, Any] | None
    current_criteria_version: int
    paused: bool
    last_decision: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "loop_count": self.loop_count,
            "last_commit": self.last_commit,
            "last_validation": self.last_validation,
            "current_criteria_version": self.current_criteria_version,
            "paused": self.paused,
            "last_decision": self.last_decision,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def load_runtime_state(path: Path) -> RuntimeState:
    if not path.exists():
        return RuntimeState(0, None, None, 1, False, "idle")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RuntimeState(
        loop_count=payload.get("loop_count", 0),
        last_commit=payload.get("last_commit"),
        last_validation=payload.get("last_validation"),
        current_criteria_version=payload.get("current_criteria_version", 1),
        paused=payload.get("paused", False),
        last_decision=payload.get("last_decision", "idle"),
    )


def save_runtime_state(path: Path, state: RuntimeState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.as_dict(), indent=2) + "\n", encoding="utf-8")
