from __future__ import annotations

from typing import Any

from generations.models import IntegrationResult, LoopPlan


class Evaluator:
    def score_loop(self, plan: LoopPlan, result: IntegrationResult) -> dict[str, float]:
        changed = result.files_merged
        code_change = min(1.0, 0.25 * len(changed))
        if any(path.startswith("games/active/") for path in changed):
            code_change = min(1.0, code_change + 0.25)
        if any(path.startswith("generations/") for path in changed):
            code_change = min(1.0, code_change + 0.15)
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
        pillar_state["game"] = {"trajectory": "on_track" if metrics["game_progress"] >= 0.5 else "unclear", "confidence": metrics["game_progress"]}
        pillar_state["self"] = {"trajectory": "on_track" if metrics["review_quality"] >= 0.7 else "unclear", "confidence": metrics["review_quality"]}
        pillar_state["website"] = {"trajectory": "on_track" if metrics["observability"] >= 0.5 else "unclear", "confidence": metrics["observability"]}
        pillar_state["tidiness"] = {"trajectory": "on_track" if passed else "off_track", "confidence": metrics["balance"]}
        updated["pillar_state"] = pillar_state
        merged = len(result.merged_tasks)
        exec_hist = dict(updated.get("execution_history", {}))
        exec_hist["recent_task_success_rate"] = round(merged / max(1, len(plan.tasks)), 2)
        exec_hist["recent_merge_success_rate"] = 1.0 if result.commit_hash else 0.0
        exec_hist["recent_validation_pass_rate"] = 1.0 if passed else 0.0
        updated["execution_history"] = exec_hist
        updated["current_loop_plan"] = None
        return updated
