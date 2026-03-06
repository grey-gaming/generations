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
        game_progress = 0.15 if plan.primary_pillar == "game" else 0.0
        if any(path.startswith("games/active/") for path in changed):
            game_progress = min(1.0, game_progress + 0.55)
        observability = 0.1
        if any(task.scope == "website" for task in result.merged_tasks):
            observability = 0.5
        if any(path.startswith("generations/src/generations/web/") for path in changed):
            observability = min(1.0, observability + 0.2)
        review_quality = 1.0 if all(item.success for item in result.validation) and result.validation else 0.3
        creativity = 0.35 + 0.15 * len(result.merged_tasks)
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
        if passed and result.commit_hash:
            outcomes["pass_count"] = outcomes.get("pass_count", 0) + 1
            outcomes["last_successful_loop"] = plan.loop_counter
            outcomes["last_error"] = None
        elif not passed:
            outcomes["fail_count"] = outcomes.get("fail_count", 0) + 1
            outcomes["last_error"] = result.validation[-1].output if result.validation else "validation failed"
        outcomes["last_validation"] = [item.as_dict() for item in result.validation]
        updated["outcomes"] = outcomes

        eval_metrics = dict(updated.get("evaluation_metrics", {}))
        history = list(eval_metrics.get("recent_history", []))
        history.append({"loop": plan.loop_counter, "metrics": metrics, "theme": plan.theme, "primary_pillar": plan.primary_pillar})
        history = history[-10:]
        rolling = {}
        for key in metrics:
            values = [float(item["metrics"].get(key, 0.0)) for item in history]
            rolling[key] = round(sum(values) / len(values), 2) if values else 0.0
        eval_metrics["current"] = metrics
        eval_metrics["rolling_average"] = rolling
        eval_metrics["recent_history"] = history
        updated["evaluation_metrics"] = eval_metrics

        pillars = dict(updated.get("pillars", {}))
        game_paths = [path for path in result.files_merged if path.startswith("games/active/")]
        platform_paths = [path for path in result.files_merged if path.startswith("generations/")]
        website_paths = [path for path in result.files_merged if path.startswith("generations/src/generations/web/")]
        monetization_paths = [path for path in result.files_merged if "monet" in path.lower() or "support" in path.lower()]
        pillars["self"] = {
            "summary": (pillars.get("self") or {}).get("summary", ""),
            "trajectory": "on_track" if (plan.primary_pillar == "self" and bool(result.commit_hash)) or metrics["review_quality"] >= 0.7 else "unclear",
            "confidence": max(metrics["review_quality"], metrics["observability"]),
            "current_state": f"{len(platform_paths)} platform file(s) and {len(website_paths)} website file(s) merged in service of the current block.",
            "biggest_risk": "Self work can become abstract if it stops producing clearer execution loops.",
        }
        pillars["game"] = {
            "summary": (pillars.get("game") or {}).get("summary", ""),
            "trajectory": "on_track" if metrics["game_progress"] >= 0.5 else "unclear",
            "confidence": metrics["game_progress"],
            "current_state": f"{len(game_paths)} active-game file(s) merged this loop.",
            "biggest_risk": "Game work can stay descriptive unless the block forces executable artifacts.",
        }
        pillars["monetization_platform"] = {
            "summary": (pillars.get("monetization_platform") or {}).get("summary", ""),
            "trajectory": "on_track" if plan.primary_pillar == "monetization_platform" and bool(result.commit_hash) else "unclear",
            "confidence": 0.6 if monetization_paths else 0.3,
            "current_state": f"{len(monetization_paths)} monetization-facing file(s) changed recently.",
            "biggest_risk": "Commercial framing can outpace evidence if it is not anchored to real progress.",
        }
        updated["pillars"] = pillars

        exec_hist = dict(updated.get("execution_history", {}))
        exec_hist["recent_task_success_rate"] = round(len(result.merged_tasks) / max(1, len(plan.tasks)), 2)
        exec_hist["recent_merge_success_rate"] = 1.0 if result.commit_hash else 0.0
        exec_hist["recent_validation_pass_rate"] = 1.0 if passed else 0.0
        updated["execution_history"] = exec_hist
        return updated
