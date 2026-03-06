from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TaskScope = Literal["platform", "active_game", "website", "cross_cutting"]
TaskStatus = Literal["planned", "running", "merged", "rejected", "failed", "no_change"]
Trajectory = Literal["on_track", "unclear", "off_track"]


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
    scope: TaskScope
    objective: str
    allowed_paths: list[str]
    success_signal: str
    priority: int
    status: TaskStatus = "planned"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LoopPlan:
    loop_counter: int
    theme: str
    goal: str
    pillar_budget: dict[str, float]
    tasks: list[ExecutionTask]
    integration_policy: dict[str, Any]
    planning_loop: int
    horizon_10_theme: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tasks"] = [task.as_dict() for task in self.tasks]
        return payload


@dataclass(slots=True)
class TaskResult:
    task_id: str
    scope: TaskScope
    objective: str
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
        return asdict(self)


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
class PlanningRecord:
    planning_loop: int
    generated_at: str
    good_end_state: dict[str, str]
    pillar_assessment: dict[str, dict[str, Any]]
    horizon_10: dict[str, Any]
    horizon_100: dict[str, Any]
    horizon_250: dict[str, Any]
    retro: dict[str, Any]
    planner_rationale: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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
