from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

from generations.models import CurrentLoopPlan, RuntimeSnapshot


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_runtime() -> dict[str, Any]:
    return RuntimeSnapshot(0, None, None, 1, False, "idle").as_dict()


def load_runtime(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_runtime()
    payload = json.loads(path.read_text(encoding="utf-8"))
    base = default_runtime()
    base.update(payload)
    return base


def save_runtime(path: Path, state: RuntimeSnapshot | dict[str, Any]) -> None:
    payload = state.as_dict() if isinstance(state, RuntimeSnapshot) else dict(state)
    payload["updated_at"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_runtime_state(path: Path) -> RuntimeSnapshot:
    payload = load_runtime(path)
    return RuntimeSnapshot(
        loop_count=payload.get("loop_count", 0),
        last_commit=payload.get("last_commit"),
        last_validation=payload.get("last_validation"),
        current_criteria_version=payload.get("current_criteria_version", 1),
        paused=payload.get("paused", False),
        last_decision=payload.get("last_decision", "idle"),
    )


def save_runtime_state(path: Path, state: RuntimeSnapshot) -> None:
    save_runtime(path, state)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_current_loop_plan(path: Path) -> dict[str, Any]:
    return load_json(path, default={})


def save_current_loop_plan(path: Path, plan: CurrentLoopPlan | dict[str, Any]) -> None:
    payload = plan.as_dict() if isinstance(plan, CurrentLoopPlan) else dict(plan)
    if not payload.get("updated_at"):
        payload["updated_at"] = now_iso()
    save_json(path, payload)
