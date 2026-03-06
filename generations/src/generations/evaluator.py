from __future__ import annotations

from typing import Any

from generations.models import IntegrationResult, LoopPlan


class Evaluator:
    def score_loop(self, plan: LoopPlan, result: IntegrationResult) -> dict[str, float]:
        changed = result.files_merged
        changed_count = len(changed)
        code_change = min(1.0, 0.2 * changed_count)
        if any(path.startswith("games/active/") for path in changed):
            code_change = min(1.0, code_change + 0.35)
        if any(path.startswith("generations/") for path in changed):
            code_change = min(1.0, code_change + 0.2)
        game_progress = 0.2 if any(task.scope == "active_game" for task in result.merged_tasks) else 0.0
        if any(path.startswith("games/active/") for path in changed):
            game_progress = min(1.0, game_progress + 0.5)
        observability = 0.2 if any(task.scope == "website" for task in result.merged_tasks) else 0.1
        review_quality = 1.0 if all(item.success for item in result.validation) and result.validation else 0.3
        creativity = 0.4 + 0.15 * len(result.merged_tasks)
        balance = max(0.0, 1.0 - (max([creativity, code_change, review_quality, game_progress, observability]) - min([creativity, code_change, review_quality, game_progress, observability])))
        return {
            "creativity": round(min(1.0, creativity), 2),
            "code_change": round(code_change, 2),
            "review_quality": round(review_quality, 2),
            "game_progress": round(game_progress, 2),
            "observability": round(observability, 2),
            "balance": round(balance, 2),
        }

    def update_memory(self, memory: dict[str, Any], plan: LoopPlan, result: IntegrationResult, metrics: dict[str, float]) -> dict[str, Any]:
        updated = dict(memory)
        outcomes = dict(updated.get("outcomes", {}))
        passed = all(item.success for item in result.validation)
        if passed:
            outcomes["pass_count"] = outcomes.get("pass_count", 0) + 1
            outcomes["last_successful_loop"] = plan.loop_counter
            outcomes["last_error"] = None
        else:
            outcomes["fail_count"] = outcomes.get("fail_count", 0) + 1
            outcomes["last_error"] = result.validation[-1].output if result.validation else "validation failed"
        outcomes["last_validation"] = [item.as_dict() for item in result.validation]
        updated["outcomes"] = outcomes
        eval_metrics = dict(updated.get("evaluation_metrics", {}))
        history = list(eval_metrics.get("recent_history", []))
        history.append({"loop": plan.loop_counter, "metrics": metrics, "theme": plan.theme})
        history = history[-10:]
        rolling = {}
        for key in metrics:
            values = [float(item["metrics"].get(key, 0.0)) for item in history]
            rolling[key] = round(sum(values) / len(values), 2) if values else 0.0
        eval_metrics["current"] = metrics
        eval_metrics["rolling_average"] = rolling
        eval_metrics["recent_history"] = history
        updated["evaluation_metrics"] = eval_metrics
        pillar_state = dict(updated.get("pillar_state", {}))
        game_paths = [path for path in result.files_merged if path.startswith("games/active/")]
        platform_paths = [path for path in result.files_merged if path.startswith("generations/")]
        website_paths = [path for path in result.files_merged if path.startswith("generations/src/generations/web/")]
        pillar_state["game"] = {
            "trajectory": "on_track" if metrics["game_progress"] >= 0.5 else "unclear",
            "confidence": metrics["game_progress"],
            "current_state": f"{len(game_paths)} active-game file(s) merged this loop.",
            "biggest_risk": "Game progress is stalling." if not game_paths else "Need to turn structural progress into playable behavior.",
        }
        pillar_state["self"] = {
            "trajectory": "on_track" if metrics["review_quality"] >= 0.7 else "unclear",
            "confidence": metrics["review_quality"],
            "current_state": f"{len(platform_paths)} platform file(s) merged with review score {metrics['review_quality']:.2f}.",
            "biggest_risk": "Platform work is not landing consistently." if not platform_paths else "Platform improvements may outrun product value.",
        }
        pillar_state["website"] = {
            "trajectory": "on_track" if metrics["observability"] >= 0.5 else "unclear",
            "confidence": metrics["observability"],
            "current_state": f"{len(website_paths)} website file(s) merged this loop.",
            "biggest_risk": "The public journey is not reflecting current loop reality." if not website_paths else "Website work could crowd out product work.",
        }
        pillar_state["tidiness"] = {
            "trajectory": "on_track" if passed and bool(result.commit_hash) else "off_track",
            "confidence": metrics["balance"],
            "current_state": "Loop produced a validated commit." if result.commit_hash else "Loop did not produce a new validated commit.",
            "biggest_risk": "No-op loops or validation failures are eroding momentum." if not result.commit_hash else "Repo health depends on keeping changes coherent.",
        }
        updated["pillar_state"] = pillar_state
        merged = len(result.merged_tasks)
        exec_hist = dict(updated.get("execution_history", {}))
        exec_hist["recent_task_success_rate"] = round(merged / max(1, len(plan.tasks)), 2)
        exec_hist["recent_merge_success_rate"] = 1.0 if result.commit_hash else 0.0
        exec_hist["recent_validation_pass_rate"] = 1.0 if passed else 0.0
        updated["execution_history"] = exec_hist
        updated["current_loop_plan"] = None
        return updated
