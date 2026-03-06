from __future__ import annotations

from typing import Any


def visible_journal_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("entry_type") not in {"rest", "rest_cycle"}]


def build_dashboard_context(
    runtime: dict[str, Any],
    current_loop_plan: dict[str, Any],
    memory: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    active_game = memory.get("active_game") or {}
    metrics = ((memory.get("evaluation_metrics") or {}).get("rolling_average") or {})
    outcomes = memory.get("outcomes") or {}
    pillars = memory.get("pillars") or {}
    vision = (memory.get("long_term_vision") or {}).get("current") or {}
    block_plan = (memory.get("block_planning") or {}).get("current") or {}
    retrospective = (memory.get("retrospectives") or {}).get("latest") or {}
    tasks = current_loop_plan.get("tasks") or []
    latest_loop = next((entry for entry in entries if entry.get("entry_type") == "loop"), None)
    latest_diary = (latest_loop or {}).get("diary") or {}
    latest_provider = (((latest_loop or {}).get("provider") or {}).get("planner") or {})

    return {
        "hero": {
            "game_name": active_game.get("name", "Unknown game"),
            "thesis": active_game.get("current_thesis", "No active thesis yet."),
            "vision_version": (memory.get("long_term_vision") or {}).get("current_version", 0),
            "loop_count": runtime.get("loop_count", 0),
            "last_validation": runtime.get("last_validation") or "unknown",
            "last_commit": runtime.get("last_commit") or "No commit yet",
            "model": latest_provider.get("model") or "qwen3.5:397b-cloud",
            "provider": latest_provider.get("provider") or "ollama_cloud",
        },
        "now": {
            "block_id": block_plan.get("block_id") or 0,
            "primary_pillar": block_plan.get("primary_pillar") or "self",
            "execution_range": _range_text(block_plan.get("execution_range") or []),
            "why_now": block_plan.get("why_this_pillar_now") or "No active block plan yet.",
            "current_goal": current_loop_plan.get("goal") or "No active loop goal.",
            "working_on": current_loop_plan.get("working_on") or "Not labeled yet.",
            "pass_count": outcomes.get("pass_count", 0),
            "fail_count": outcomes.get("fail_count", 0),
            "rest_count": outcomes.get("rest_count", 0),
        },
        "vision": {
            "index_summary": vision.get("index_summary") or "No long-term vision recorded yet.",
            "last_refined_loop": (memory.get("long_term_vision") or {}).get("last_refined_loop"),
            "pillars": [
                {
                    "name": name.replace("_", " ").title(),
                    "summary": (details or {}).get("summary", ""),
                    "purpose": _trim((details or {}).get("purpose", ""), 180),
                    "good_end_state": _trim((details or {}).get("good_end_state", ""), 180),
                }
                for name, details in (vision.get("pillars") or {}).items()
            ],
        },
        "block": {
            "title": f"Block {block_plan.get('block_id', 0)}" if block_plan else "No active block",
            "primary_pillar": (block_plan.get("primary_pillar") or "self").replace("_", " "),
            "outcomes": block_plan.get("target_outcomes") or [],
            "support_work": block_plan.get("allowed_support_work") or [],
            "non_goals": block_plan.get("explicit_non_goals") or [],
            "review_focus": block_plan.get("review_focus") or [],
        },
        "current_loop": {
            "theme": current_loop_plan.get("theme") or "No active loop theme",
            "goal": current_loop_plan.get("goal") or "No active loop goal",
            "working_on": current_loop_plan.get("working_on") or "Not labeled yet",
            "integration_status": current_loop_plan.get("integration_status") or "idle",
            "validation_status": current_loop_plan.get("validation_status") or "idle",
            "tasks": [_task_card(task) for task in tasks],
            "summary": _loop_summary(tasks),
        },
        "retrospective": {
            "summary": retrospective.get("summary") or "No retrospective recorded yet.",
            "wins": retrospective.get("wins") or [],
            "stalls": retrospective.get("stalls") or [],
            "change_next_time": retrospective.get("change_next_time") or [],
        },
        "pillars": [
            {
                "name": name.replace("_", " ").title(),
                "trajectory": (details or {}).get("trajectory", "unclear").replace("_", " "),
                "confidence": int(round(float((details or {}).get("confidence", 0.0)) * 100)),
                "current_state": (details or {}).get("current_state", "Assessment unavailable."),
                "risk": (details or {}).get("biggest_risk", "Assessment unavailable."),
            }
            for name, details in pillars.items()
        ],
        "support": {
            "summary": "Support remains honest, minimal, and subordinate to proving the platform and the game.",
            "disclosure": "Monetization strategy is part of the long-term vision, but it should follow evidence rather than lead it.",
            "current_experiment": _current_experiment(memory),
        },
        "diary": {
            "latest_entry": latest_diary.get("entry") or "No diary entry yet.",
            "mood": latest_diary.get("mood") or "observing",
            "next_desire": latest_diary.get("next_desire") or "Keep the next loop coherent.",
        },
        "metrics": [
            {"name": "Creativity", "value": _percent(metrics.get("creativity", 0.0)), "hint": "Novel direction and useful variation inside the current block."},
            {"name": "Code Change", "value": _percent(metrics.get("code_change", 0.0)), "hint": "Real repository files merged, especially under generations/ and games/active/."},
            {"name": "Review", "value": _percent(metrics.get("review_quality", 0.0)), "hint": "How well recent loops passed validation and review gates."},
            {"name": "Game", "value": _percent(metrics.get("game_progress", 0.0)), "hint": "Progress toward a playable game artifact when the active block is game-facing."},
            {"name": "Observability", "value": _percent(metrics.get("observability", 0.0)), "hint": "How legibly the system reports its plans, progress, and constraints."},
            {"name": "Balance", "value": _percent(metrics.get("balance", 0.0)), "hint": "Whether recent loops spread effort sensibly without losing the block identity."},
        ],
    }


def entry_body(entry: dict[str, Any]) -> str:
    entry_type = entry.get("entry_type")
    if entry_type == "loop":
        diary = entry.get("diary") or {}
        if isinstance(diary, dict) and diary.get("entry"):
            return str(diary.get("entry"))
        proposal = entry.get("proposal") or {}
        if isinstance(proposal, dict):
            return str(proposal.get("goal") or proposal.get("theme") or "Loop recorded.")
    if entry_type == "block_planning":
        block_plan = entry.get("block_plan") or {}
        if isinstance(block_plan, dict):
            return f"Block {block_plan.get('block_id', '?')} planned around {block_plan.get('primary_pillar', 'self')}."
    if entry_type == "retrospective":
        retro = entry.get("retrospective") or {}
        if isinstance(retro, dict):
            return str(retro.get("summary") or "Retrospective recorded.")
    if entry_type in {"vision", "vision_refinement"}:
        vision = entry.get("long_term_vision") or {}
        if isinstance(vision, dict):
            return str(vision.get("index_summary") or "Long-term vision recorded.")
    return "Entry recorded."


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
        return "This loop is planning or resting rather than executing task work."
    changed = sum(1 for task in tasks if task.get("changed_files"))
    stalled = sum(1 for task in tasks if task.get("status") in {"no_change", "failed", "rejected"})
    return f"{changed} task(s) changed the repo; {stalled} task(s) stalled or produced no change."


def _current_experiment(memory: dict[str, Any]) -> str:
    experiments = memory.get("monetization_experiments") or []
    if not experiments:
        return "No monetization experiment is active."
    current = experiments[-1]
    return str(current.get("reason") or current.get("name") or "Support placeholder active.")


def _trim(value: str, width: int) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= width:
        return compact
    return compact[: width - 3] + "..."


def _range_text(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{value[0]}-{value[1]}"
    return "Not scheduled"
