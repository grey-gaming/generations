from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from generations.models import BlockPlan, IntegrationResult, LongTermVisionRecord, LoopPlan, RetrospectiveRecord, TaskResult


class TUI:
    def __init__(self, debug: bool) -> None:
        self.debug = debug

    def log_run_header(self, seed_hash: str, loop_start: int, criteria_version: int, parallel_tasks: int) -> None:
        print(
            f"run start | seed={seed_hash[:12]} | loop={loop_start} | criteria=v{criteria_version} | parallel={parallel_tasks}",
            flush=True,
        )

    def log_vision(self, record: LongTermVisionRecord, meta: dict[str, Any], validation: list[Any], commit_hash: str | None) -> None:
        print("", flush=True)
        print(f"loop {record.refined_at_loop} | vision | version={record.version}", flush=True)
        print(f"goal    | Define the long-term purpose of self, game, and monetization_platform.", flush=True)
        print(f"pillars | {', '.join(record.pillars.keys())}", flush=True)
        print(f"result  | commit={(commit_hash[:10] if commit_hash else 'none')}", flush=True)
        for item in validation:
            label = "pass" if item.success else "fail"
            print(f"check   | {item.tier:<8} {label:<4} {_shorten(item.command, 92)}", flush=True)
        if self.debug:
            print(
                f"debug   | provider={meta.get('provider', '-')} model={meta.get('model', '-')} fallback={meta.get('fallback') or '-'}",
                flush=True,
            )
            if meta.get("prompt_preview"):
                print(f"          prompt={_shorten(str(meta['prompt_preview']), 108)}", flush=True)

    def log_block_plan(
        self,
        plan: BlockPlan,
        retrospective: RetrospectiveRecord | None,
        meta: dict[str, Any],
        validation: list[Any],
        commit_hash: str | None,
    ) -> None:
        print("", flush=True)
        print(f"loop {plan.planning_loop} | block-plan | block={plan.block_id} pillar={plan.primary_pillar}", flush=True)
        print(f"goal    | {_shorten(plan.why_this_pillar_now, 96)}", flush=True)
        print(f"outcomes| {', '.join(_shorten(item, 44) for item in plan.target_outcomes[:3]) or '-'}", flush=True)
        if retrospective:
            print(f"retro   | {_shorten(retrospective.summary or 'Retrospective recorded.', 96)}", flush=True)
        print(f"result  | commit={(commit_hash[:10] if commit_hash else 'none')}", flush=True)
        for item in validation:
            label = "pass" if item.success else "fail"
            print(f"check   | {item.tier:<8} {label:<4} {_shorten(item.command, 92)}", flush=True)
        if self.debug:
            print(
                f"debug   | provider={meta.get('provider', '-')} model={meta.get('model', '-')} fallback={meta.get('fallback') or '-'}",
                flush=True,
            )
            if meta.get("prompt_preview"):
                print(f"          prompt={_shorten(str(meta['prompt_preview']), 108)}", flush=True)

    def log_rest_cycle(self, loop_counter: int, reason: str, provider: dict[str, Any], advance_loop: bool) -> None:
        print("", flush=True)
        print(f"loop {loop_counter} | rest-cycle", flush=True)
        print(f"reason  | {_shorten(reason, 108)}", flush=True)
        print(f"result  | loop_advance={'yes' if advance_loop else 'no'}", flush=True)
        if self.debug:
            print(
                f"debug   | provider={provider.get('provider', '-')} model={provider.get('model', '-')} fallback={provider.get('fallback') or '-'}",
                flush=True,
            )
            if provider.get("prompt_preview"):
                print(f"          prompt={_shorten(str(provider['prompt_preview']), 108)}", flush=True)

    def log_loop_plan(self, plan: LoopPlan) -> None:
        print("", flush=True)
        print(f"loop {plan.loop_counter} | block={plan.block_id} | pillar={plan.primary_pillar} | theme: {plan.theme}", flush=True)
        print(f"goal    | {plan.goal}", flush=True)
        print(f"focus   | {plan.working_on}", flush=True)
        print(
            f"budget  | self={_pct(plan.pillar_budget.get('self'))} game={_pct(plan.pillar_budget.get('game'))} money={_pct(plan.pillar_budget.get('monetization_platform'))}",
            flush=True,
        )
        print("tasks   |", flush=True)
        for task in plan.tasks:
            print(
                f"  - {task.task_id:<16} [{task.scope:<21}] p{task.priority}  {_shorten(task.objective, 84)}",
                flush=True,
            )
        if self.debug:
            print(f"debug   | block_ref={plan.block_plan_ref} planning_mode={'yes' if plan.planning_mode else 'no'}", flush=True)

    def log_task_result(self, task_result: TaskResult) -> None:
        changed = ", ".join(task_result.changed_files[:3]) if task_result.changed_files else "-"
        print(
            f"task    | {task_result.task_id:<24} status={task_result.status:<9} changed={changed}",
            flush=True,
        )
        summary = _task_summary(task_result.summary)
        if summary:
            print(f"          {_shorten(summary, 108)}", flush=True)
        if self.debug:
            print(
                f"debug   | worktree={task_result.worktree} session={task_result.session_id or '-'}",
                flush=True,
            )
            if task_result.stdout_path or task_result.stderr_path:
                print(
                    f"          stdout={task_result.stdout_path or '-'} stderr={task_result.stderr_path or '-'}",
                    flush=True,
                )

    def log_integration(self, result: IntegrationResult, metrics: dict[str, float]) -> None:
        merged = ",".join(task.task_id for task in result.merged_tasks) or "-"
        rejected = ",".join(task.task_id for task in result.rejected_tasks) or "-"
        print(
            f"result  | merged={merged} rejected={rejected} commit={(result.commit_hash[:10] if result.commit_hash else 'none')} pushed={'yes' if result.pushed else 'no'}",
            flush=True,
        )
        print(
            "metrics | "
            f"creativity={_pct(metrics.get('creativity'))} "
            f"code={_pct(metrics.get('code_change'))} "
            f"review={_pct(metrics.get('review_quality'))} "
            f"game={_pct(metrics.get('game_progress'))} "
            f"obs={_pct(metrics.get('observability'))} "
            f"balance={_pct(metrics.get('balance'))}",
            flush=True,
        )
        for item in result.validation:
            label = "pass" if item.success else "fail"
            command = _shorten(item.command, 92)
            print(f"check   | {item.tier:<8} {label:<4} {command}", flush=True)
            if self.debug and item.output and not item.success:
                print(f"          {_shorten(item.output.replace(chr(10), ' | '), 108)}", flush=True)

    def write_debug_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _shorten(text: str, width: int) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= width:
        return compact
    return compact[: width - 3] + "..."


def _pct(value: Any) -> str:
    try:
        return f"{int(round(float(value) * 100)):>3}%"
    except (TypeError, ValueError):
        return "  0%"


def _task_summary(summary: str | None) -> str:
    if not summary:
        return ""
    if "ProviderModelNotFoundError" in summary:
        return "blocked: OpenCode could not resolve the configured Ollama model"
    if "Operation not permitted" in summary:
        return "blocked: local model endpoint could not be reached from this environment"
    return summary
