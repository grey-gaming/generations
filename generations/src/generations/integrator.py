from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Iterable

from generations.config import AppConfig
from generations.models import IntegrationResult, TaskResult, ValidationResult
from generations.validation.registry import build_validation_plan


class Integrator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.root = config.root

    def integrate(self, loop_counter: int, tasks: list[TaskResult], commit_message: str, commit_fn, push_fn) -> IntegrationResult:
        merged: list[TaskResult] = []
        rejected: list[TaskResult] = []
        files_merged: list[str] = []
        backups = self._backup_current_files(task.changed_files for task in tasks)
        try:
            for task in sorted(tasks, key=lambda item: item.task_id):
                if task.status != "merged":
                    rejected.append(task)
                    continue
                for changed in task.changed_files:
                    if not self._allowed(changed, task):
                        task.status = "rejected"
                        rejected.append(task)
                        break
                    source = self.root / task.worktree / changed
                    target = self.root / changed
                    if source.is_dir():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if source.exists():
                        shutil.copy2(source, target)
                        files_merged.append(changed)
                else:
                    merged.append(task)
            if not files_merged:
                validation = [ValidationResult(False, "policy:no-op-loop", "No repository files were merged from task worktrees.", "policy")]
                self._restore(backups)
                return IntegrationResult(merged_tasks=[], rejected_tasks=rejected + merged, files_merged=[], validation=validation, commit_hash=None, pushed=False, push_output="", rolled_back=True)
            plan = build_validation_plan(self.root, files_merged, loop_counter, self.config.test_mode)
            validation = self._run_validation(plan)
            passed = all(item.success for item in validation)
            if not passed:
                self._restore(backups)
                return IntegrationResult(merged_tasks=[], rejected_tasks=rejected + merged, files_merged=[], validation=validation, commit_hash=None, pushed=False, push_output="", rolled_back=True)
            commit_hash = commit_fn(commit_message)
            pushed, push_output = push_fn() if commit_hash else (False, "")
            return IntegrationResult(merged_tasks=merged, rejected_tasks=rejected, files_merged=sorted(set(files_merged)), validation=validation, commit_hash=commit_hash, pushed=pushed, push_output=push_output, rolled_back=False)
        except Exception:
            self._restore(backups)
            raise

    def _allowed(self, changed: str, task: TaskResult) -> bool:
        if task.scope == "platform":
            return changed.startswith("generations/")
        if task.scope == "active_game":
            return changed.startswith("games/active/")
        if task.scope == "website":
            return changed.startswith("generations/src/generations/web/") or changed.startswith("site/")
        return changed.startswith("generations/") or changed.startswith("games/active/")

    def _backup_current_files(self, groups: Iterable[Iterable[str]]) -> dict[str, bytes | None]:
        backups: dict[str, bytes | None] = {}
        for group in groups:
            for relative in group:
                if relative in backups:
                    continue
                path = self.root / relative
                backups[relative] = path.read_bytes() if path.exists() else None
        return backups

    def _restore(self, backups: dict[str, bytes | None]) -> None:
        for relative, payload in backups.items():
            path = self.root / relative
            if payload is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

    def _run_validation(self, plan) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for tier_name, commands in [("fast", plan.fast), ("targeted", plan.targeted), ("full", plan.full)]:
            for command in commands:
                completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=False)
                results.append(ValidationResult(completed.returncode == 0, " ".join(command), (completed.stdout + completed.stderr).strip(), tier_name))
        return results
