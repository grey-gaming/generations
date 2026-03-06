from __future__ import annotations

from typing import Any


def visible_journal_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("entry_type") != "rest"]


def build_dashboard_context(
    runtime: dict[str, Any],
    current_loop_plan: dict[str, Any],
    memory: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    planning = (memory.get("planning") or {}).get("current") or {}
    active_game = memory.get("active_game") or {}
    metrics = ((memory.get("evaluation_metrics") or {}).get("rolling_average") or {})
    outcomes = memory.get("outcomes") or {}
    pillar_state = memory.get("pillar_state") or {}
    tasks = current_loop_plan.get("tasks") or []
    latest_loop = next((entry for entry in entries if entry.get("entry_type") == "loop"), None)
    latest_diary = (latest_loop or {}).get("diary") or {}
    latest_provider = (((latest_loop or {}).get("provider") or {}).get("planner") or {})

    return {
        "now": {
            "loop_count": runtime.get("loop_count", 0),
            "last_validation": runtime.get("last_validation") or "unknown",
            "last_commit": runtime.get("last_commit") or "No commit yet",
            "active_game_name": active_game.get("name", "Unknown game"),
            "active_game_status": active_game.get("status", "unknown"),
            "active_game_thesis": active_game.get("current_thesis", "No active thesis yet."),
            "pass_count": outcomes.get("pass_count", 0),
            "fail_count": outcomes.get("fail_count", 0),
        },
        "loop": {
            "theme": current_loop_plan.get("theme") or "No active loop theme",
            "goal": current_loop_plan.get("goal") or "No active loop goal",
            "integration_status": current_loop_plan.get("integration_status") or "idle",
            "validation_status": current_loop_plan.get("validation_status") or "idle",
            "tasks": [_task_card(task) for task in tasks],
            "summary": _loop_summary(tasks),
            "blocking_issue": _loop_blocking_issue(tasks),
        },
        "planning": {
            "theme_10": ((planning.get("horizon_10") or {}).get("theme") or "No 10-loop theme yet"),
            "goals_10": (planning.get("horizon_10") or {}).get("goals") or [],
            "milestones_100": (planning.get("horizon_100") or {}).get("milestones") or [],
            "vision_250": (planning.get("horizon_250") or {}).get("vision") or "No long-range vision yet.",
            "pillars": [
                {
                    "name": name.title(),
                    "trajectory": (details or {}).get("trajectory", "unclear").replace("_", " "),
                    "confidence": int(round(float((details or {}).get("confidence", 0.0)) * 100)),
                    "current_state": (details or {}).get("current_state", "Assessment unavailable."),
                    "risk": (details or {}).get("biggest_risk", "Assessment unavailable."),
                }
                for name, details in pillar_state.items()
            ],
        },
        "support": {
            "summary": "Support is experimental, honest, and secondary to proving the game and the platform.",
            "disclosure": "Any monetization changes are logged, reversible, and kept free of dark patterns.",
            "current_experiment": _current_experiment(memory),
        },
        "diary": {
            "latest_entry": latest_diary.get("entry") or "No diary entry yet.",
            "mood": latest_diary.get("mood") or "observing",
            "next_desire": latest_diary.get("next_desire") or "Keep the next loop coherent.",
        },
        "status_strip": {
            "model": latest_provider.get("model") or "qwen3.5:397b-cloud",
            "provider": latest_provider.get("provider") or "ollama_cloud",
            "fallback": latest_provider.get("fallback"),
            "metrics": [
                {"name": "Creativity", "value": _percent(metrics.get("creativity", 0.0)), "hint": "Novel direction and useful variation in recent loops."},
                {"name": "Code Change", "value": _percent(metrics.get("code_change", 0.0)), "hint": "Real repository files merged this loop, especially under generations/ and games/active/."},
                {"name": "Review", "value": _percent(metrics.get("review_quality", 0.0)), "hint": "How well recent loops passed validation and review gates."},
                {"name": "Game", "value": _percent(metrics.get("game_progress", 0.0)), "hint": "Progress inside the active game workspace toward a playable build."},
                {"name": "Observability", "value": _percent(metrics.get("observability", 0.0)), "hint": "How clearly the system reports what it is doing."},
                {"name": "Balance", "value": _percent(metrics.get("balance", 0.0)), "hint": "Whether progress is spread sensibly across the pillars."},
            ],
        },
    }


def _percent(value: Any) -> int:
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return 0


def _task_card(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("task_id", "?"),
        "scope": str(task.get("scope", "unknown")).replace("_", " "),
        "objective": task.get("objective", "No objective recorded."),
        "status": task.get("status", "unknown").replace("_", " "),
        "changed_files": task.get("changed_files") or [],
        "summary": _task_summary(task),
    }


def _task_summary(task: dict[str, Any]) -> str:
    changed = task.get("changed_files") or []
    if changed:
        return f"Changed {len(changed)} file{'s' if len(changed) != 1 else ''}."
    summary = str(task.get("summary") or "")
    if "ProviderModelNotFoundError" in summary:
        return "Blocked: OpenCode could not find the configured Ollama model."
    if task.get("status") == "merged":
        return "Task reported success, but no repository files were merged."
    if task.get("status") == "no_change":
        return "No repository change landed in this task."
    return summary or "Task recorded."


def _loop_summary(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "No task plan is active."
    changed = sum(1 for task in tasks if task.get("changed_files"))
    blocked = sum(
        1
        for task in tasks
        if task.get("status") in {"no_change", "failed", "rejected"} or (task.get("status") == "merged" and not task.get("changed_files"))
    )
    return f"{changed} task(s) changed the repo; {blocked} task(s) stalled or produced no change."


def _loop_blocking_issue(tasks: list[dict[str, Any]]) -> str | None:
    for task in tasks:
        summary = str(task.get("summary") or "")
        if "ProviderModelNotFoundError" in summary:
            return "OpenCode is pointed at an Ollama model name it cannot resolve."
    return None


def _current_experiment(memory: dict[str, Any]) -> str:
    experiments = memory.get("monetization_experiments") or []
    if not experiments:
        return "No monetization experiment is active."
    current = experiments[-1]
    return str(current.get("reason") or current.get("name") or "Support placeholder active.")
