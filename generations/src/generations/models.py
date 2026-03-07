from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TaskRoute = Literal["platform", "active_game", "website", "cross_cutting", "monetization_platform"]
TaskStatus = Literal["planned", "running", "merged", "rejected", "failed", "no_change"]
Trajectory = Literal["on_track", "unclear", "off_track"]
PrimaryPillar = Literal["self", "game", "monetization_platform"]
BlockAlignment = Literal["aligned", "supporting", "drifting"]
PillarAlignment = Literal["primary", "supporting", "drifting"]


@dataclass(slots=True)
class ValidationResult:
    success: bool
    command: str
    output: str
    tier: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionTask:
    task_id: str
    intent_label: str
    execution_route: TaskRoute
    objective: str
    allowed_paths: list[str]
    success_signal: str
    priority: int
    support_reason: str = ""
    pillar_alignment: PillarAlignment = "primary"
    status: TaskStatus = "planned"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scope"] = self.execution_route
        return payload

    @property
    def scope(self) -> TaskRoute:
        return self.execution_route

    @scope.setter
    def scope(self, value: TaskRoute) -> None:
        self.execution_route = value

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ExecutionTask":
        route = str(payload.get("execution_route") or payload.get("scope") or "platform")
        intent = str(payload.get("intent_label") or payload.get("scope") or "platform")
        return cls(
            task_id=str(payload.get("task_id") or "A"),
            intent_label=intent,
            execution_route=route,  # normalized upstream
            objective=str(payload.get("objective") or "Advance the active block with one coherent change."),
            allowed_paths=[str(item) for item in (payload.get("allowed_paths") or [])],
            success_signal=str(payload.get("success_signal") or "A coherent repository change lands."),
            priority=int(payload.get("priority") or 1),
            support_reason=str(payload.get("support_reason") or "Supports the current block objective."),
            pillar_alignment=str(payload.get("pillar_alignment") or "primary"),  # normalized upstream
            status=str(payload.get("status") or "planned"),
        )


@dataclass(slots=True)
class LoopPlan:
    loop_counter: int
    theme: str
    goal: str
    working_on: str
    primary_pillar: PrimaryPillar
    block_id: int
    planning_mode: bool
    block_plan_ref: int
    support_task_policy: dict[str, Any]
    pillar_budget: dict[str, float]
    block_alignment: BlockAlignment
    drift_reason: str
    tasks: list[ExecutionTask]
    integration_policy: dict[str, Any]
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tasks"] = [task.as_dict() for task in self.tasks]
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "LoopPlan":
        return cls(
            loop_counter=int(payload.get("loop_counter") or 0),
            theme=str(payload.get("theme") or "Current block"),
            goal=str(payload.get("goal") or "Advance the active block."),
            working_on=str(payload.get("working_on") or "current_block"),
            primary_pillar=str(payload.get("primary_pillar") or "self"),
            block_id=int(payload.get("block_id") or 0),
            planning_mode=bool(payload.get("planning_mode", False)),
            block_plan_ref=int(payload.get("block_plan_ref") or payload.get("block_id") or 0),
            support_task_policy=dict(payload.get("support_task_policy") or {"requires_justification": True}),
            pillar_budget={str(key): float(value) for key, value in dict(payload.get("pillar_budget") or {}).items()},
            block_alignment=str(payload.get("block_alignment") or "aligned"),
            drift_reason=str(payload.get("drift_reason") or ""),
            tasks=[ExecutionTask.from_payload(item) for item in (payload.get("tasks") or [])],
            integration_policy=dict(payload.get("integration_policy") or {"merge_order": [], "allow_partial_success": True}),
            rationale=str(payload.get("rationale") or "Execution loop aligns to the active block."),
        )


@dataclass(slots=True)
class TaskResult:
    task_id: str
    intent_label: str
    execution_route: TaskRoute
    objective: str
    allowed_paths: list[str]
    worktree: str
    branch: str
    changed_files: list[str]
    status: TaskStatus
    session_id: str | None
    session_export: str | None
    stdout_path: str | None
    stderr_path: str | None
    summary: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scope"] = self.execution_route
        return payload

    @property
    def scope(self) -> TaskRoute:
        return self.execution_route


@dataclass(slots=True)
class IntegrationResult:
    merged_tasks: list[TaskResult]
    rejected_tasks: list[TaskResult]
    files_merged: list[str]
    validation: list[ValidationResult]
    commit_hash: str | None
    pushed: bool
    push_output: str
    rolled_back: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "merged_tasks": [task.as_dict() for task in self.merged_tasks],
            "rejected_tasks": [task.as_dict() for task in self.rejected_tasks],
            "files_merged": self.files_merged,
            "validation": [item.as_dict() for item in self.validation],
            "commit_hash": self.commit_hash,
            "pushed": self.pushed,
            "push_output": self.push_output,
            "rolled_back": self.rolled_back,
        }


@dataclass(slots=True)
class VisionPillar:
    name: PrimaryPillar
    purpose: str
    good_end_state: str
    failure_modes: list[str]
    relationships: list[str]
    content: str
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LongTermVisionRecord:
    version: int
    generated_at: str
    refined_at_loop: int
    index_summary: str
    pillars: dict[str, dict[str, Any]]
    change_summary: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BlockPlan:
    block_id: int
    planning_loop: int
    execution_range: tuple[int, int]
    primary_pillar: PrimaryPillar
    why_this_pillar_now: str
    target_outcomes: list[str]
    sub_goals: list[str]
    allowed_support_work: list[str]
    explicit_non_goals: list[str]
    success_signals: list[str]
    failure_signals: list[str]
    expected_artifacts: list[str]
    metrics_to_watch: list[str]
    risks: list[str]
    review_focus: list[str]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_range"] = list(self.execution_range)
        return payload


@dataclass(slots=True)
class RetrospectiveRecord:
    block_id: int
    retrospective_loop: int
    primary_pillar: PrimaryPillar
    execution_range: tuple[int, int]
    intended_outcomes: list[str]
    actual_outcomes: list[str]
    wins: list[str]
    failures: list[str]
    stalls: list[str]
    surprises: list[str]
    metric_reflection: dict[str, list[str]]
    carry_forward: list[str]
    change_next_time: list[str]
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_range"] = list(self.execution_range)
        return payload


@dataclass(slots=True)
class DiaryEntry:
    title: str
    mood: str
    entry: str
    hopes: list[str]
    worries: list[str]
    lessons: list[str]
    next_desire: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CurrentLoopPlan:
    loop_counter: int
    theme: str
    goal: str
    working_on: str = ""
    primary_pillar: str = "self"
    block_alignment: str = "aligned"
    drift_reason: str = ""
    block_id: int = 0
    tasks: list[dict[str, Any]] = field(default_factory=list)
    integration_status: str = "pending"
    validation_status: str = "pending"
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeSnapshot:
    loop_count: int
    last_commit: str | None
    last_validation: dict[str, Any] | None
    current_criteria_version: int
    paused: bool
    last_decision: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
