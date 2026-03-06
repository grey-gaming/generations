from __future__ import annotations

from pathlib import Path

from generations.adapters.ollama_cloud import OllamaCloudAdapter
from generations.models import ExecutionTask, LoopPlan
from generations.runner import Runner


def test_runner_rejects_invalid_task_scopes(tmp_path: Path) -> None:
    runner = Runner(tmp_path, "seed", debug=False, parallel_tasks=1)
    plan = LoopPlan(
        loop_counter=2,
        theme="Bad plan",
        goal="Should be rejected",
        primary_pillar="self",
        block_id=1,
        planning_mode=False,
        block_plan_ref=1,
        support_task_policy={"requires_justification": True},
        pillar_budget={"self": 1.0},
        tasks=[
            ExecutionTask(
                task_id="A",
                scope="platform",  # type: ignore[arg-type]
                objective="ok",
                allowed_paths=["generations/"],
                success_signal="ok",
                priority=1,
            )
        ],
        integration_policy={"merge_order": ["A"], "allow_partial_success": True},
        rationale="r",
    )
    assert runner._validate_loop_plan(plan) is None
    plan.tasks[0].scope = "vision/long_term_vision.json"  # type: ignore[assignment]
    assert runner._validate_loop_plan(plan) == "Planner produced invalid task scopes for task(s): A."


def test_ollama_adapter_normalizes_semantic_task_scopes() -> None:
    adapter = OllamaCloudAdapter(debug=False)
    assert adapter._normalize_scope("validation_hooks") == "platform"
    assert adapter._normalize_scope("journey_page") == "website"
    assert adapter._normalize_scope("simulation") == "active_game"
    assert adapter._normalize_scope("support") == "monetization_platform"
