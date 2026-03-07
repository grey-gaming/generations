from __future__ import annotations

from pathlib import Path

from generations.adapters.ollama_cloud import OllamaCloudAdapter
from generations.models import ExecutionTask, LoopPlan
from generations.runner import Runner


def test_runner_validates_execution_routes_and_drift_metadata(tmp_path: Path) -> None:
    runner = Runner(tmp_path, "seed", debug=False, parallel_tasks=1)
    plan = LoopPlan(
        loop_counter=2,
        theme="Bad plan",
        goal="Should be rejected",
        working_on="bad_plan",
        primary_pillar="self",
        block_id=1,
        planning_mode=False,
        block_plan_ref=1,
        support_task_policy={"requires_justification": True},
        pillar_budget={"self": 1.0},
        block_alignment="aligned",
        drift_reason="",
        tasks=[
            ExecutionTask(
                task_id="A",
                intent_label="planner_hardening",
                execution_route="platform",  # type: ignore[arg-type]
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
    plan.tasks[0].execution_route = "vision/long_term_vision.json"  # type: ignore[assignment]
    assert runner._validate_loop_plan(plan) == "Planner produced invalid execution routes for task(s): A."
    plan.tasks[0].execution_route = "platform"  # type: ignore[assignment]
    plan.block_alignment = "drifting"
    assert runner._validate_loop_plan(plan) == "Planner marked the loop as drifting but omitted drift_reason."


def test_ollama_adapter_infers_routes_from_semantic_intent_labels() -> None:
    adapter = OllamaCloudAdapter(debug=False)
    assert adapter._infer_execution_route(intent_label="validation_hooks", allowed_paths=[], objective="Tighten validation", primary_pillar="self") == "platform"
    assert adapter._infer_execution_route(intent_label="ci_cd_infrastructure", allowed_paths=[], objective="Improve CI", primary_pillar="self") == "platform"
    assert adapter._infer_execution_route(intent_label="journey_page", allowed_paths=[], objective="Update the site", primary_pillar="self") == "website"
    assert adapter._infer_execution_route(intent_label="simulation", allowed_paths=[], objective="Advance the simulation", primary_pillar="game") == "active_game"
    assert adapter._infer_execution_route(intent_label="support", allowed_paths=[], objective="Clarify support", primary_pillar="monetization_platform") == "monetization_platform"
    assert adapter._infer_execution_route(intent_label="data_architecture", allowed_paths=[], objective="Clarify data architecture", primary_pillar="self") == "platform"
    assert adapter._infer_execution_route(intent_label="data_schema_and_persistence_layer", allowed_paths=[], objective="Stabilize persistence", primary_pillar="self") == "platform"


def test_ollama_adapter_normalizes_working_on_label() -> None:
    adapter = OllamaCloudAdapter(debug=False)
    assert adapter._normalize_working_on("Validation Pipeline") == "validation_pipeline"
    assert adapter._normalize_working_on("ci/cd infrastructure") == "ci_cd_infrastructure"


def test_ollama_adapter_normalizes_task_without_scope_field() -> None:
    adapter = OllamaCloudAdapter(debug=False)
    task = adapter._normalize_task(
        {
            "task_id": "A",
            "intent_label": "data_schema_and_persistence_layer",
            "objective": "Define a persistence interface",
            "allowed_paths": ["generations/src/generations", "generations/tests"],
            "success_signal": "Persistence work lands",
            "priority": 1,
        },
        primary_pillar="self",
    )
    assert task["intent_label"] == "data_schema_and_persistence_layer"
    assert task["execution_route"] == "platform"
    assert task["allowed_paths"] == ["generations/src/generations", "generations/tests"]
