from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from generations.models import CurrentLoopPlan, IntegrationResult, LoopPlan, TaskResult


class TUI:
    def __init__(self, debug: bool) -> None:
        self.debug = debug

    def log_run_header(self, seed_hash: str, loop_start: int, criteria_version: int, parallel_tasks: int) -> None:
        print(f"run start: seed_sha={seed_hash[:12]} loop_start={loop_start} criteria_v={criteria_version} parallel_tasks={parallel_tasks}", flush=True)

    def log_loop_plan(self, plan: LoopPlan) -> None:
        print(f"loop={plan.loop_counter} theme={plan.theme}", flush=True)
        print(f"goal: {plan.goal}", flush=True)
        for task in plan.tasks:
            print(f"task {task.task_id}: scope={task.scope} priority={task.priority} objective={task.objective}", flush=True)

    def log_task_result(self, task_result: TaskResult) -> None:
        print(f"task {task_result.task_id}: status={task_result.status} changed={','.join(task_result.changed_files) or '-'}", flush=True)
        if self.debug:
            print(f"debug task {task_result.task_id}: worktree={task_result.worktree} session={task_result.session_id or '-'} stdout={task_result.stdout_path or '-'} stderr={task_result.stderr_path or '-'}", flush=True)

    def log_integration(self, result: IntegrationResult, metrics: dict[str, float]) -> None:
        merged = ",".join(task.task_id for task in result.merged_tasks) or "-"
        rejected = ",".join(task.task_id for task in result.rejected_tasks) or "-"
        print(f"integration: merged={merged} rejected={rejected} commit={result.commit_hash[:10] if result.commit_hash else 'none'}", flush=True)
        print(
            "metrics: "
            f"creativity={metrics.get('creativity', 0):.2f} "
            f"code_change={metrics.get('code_change', 0):.2f} "
            f"review={metrics.get('review_quality', 0):.2f} "
            f"game={metrics.get('game_progress', 0):.2f} "
            f"obs={metrics.get('observability', 0):.2f} "
            f"balance={metrics.get('balance', 0):.2f}",
            flush=True,
        )
        for item in result.validation:
            print(f"validation[{item.tier}]: {'pass' if item.success else 'fail'} {item.command}", flush=True)

    def write_debug_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
