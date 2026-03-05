from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import subprocess
from typing import Callable

from generations.models import OpenCodePlan, ValidationResult


@dataclass(slots=True)
class OpenCodeResult:
    plan: OpenCodePlan
    files_touched: list[str]
    validation: list[ValidationResult]
    commit_hash: str | None
    committed: bool
    rolled_back: bool


class OpenCodeAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_workflow(
        self,
        plan: OpenCodePlan,
        apply_fn: Callable[[], list[str]],
        verify_commands: list[list[str]],
        commit_message: str,
    ) -> OpenCodeResult:
        backup_dir = self.root / ".generations_tmp_backup"
        backups = self._snapshot_files(plan.files_expected, backup_dir)
        files_touched = apply_fn()
        validation = [self._run_command(cmd) for cmd in verify_commands]
        if not all(item.success for item in validation):
            self._restore_files(backups, backup_dir)
            return OpenCodeResult(plan, files_touched, validation, None, False, True)
        commit_hash = self._commit(commit_message)
        shutil.rmtree(backup_dir, ignore_errors=True)
        return OpenCodeResult(plan, files_touched, validation, commit_hash, commit_hash is not None, False)

    def _run_command(self, command: list[str]) -> ValidationResult:
        completed = subprocess.run(
            command,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (completed.stdout + completed.stderr).strip()
        return ValidationResult(
            success=completed.returncode == 0,
            command=" ".join(command),
            output=output,
        )

    def _commit(self, message: str) -> str | None:
        subprocess.run(["git", "add", "."], cwd=self.root, check=False, capture_output=True)
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.root,
            check=False,
            capture_output=True,
        )
        if diff.returncode == 0:
            return self._head_commit()
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        return self._head_commit()

    def _head_commit(self) -> str | None:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()

    def _snapshot_files(self, files_touched: list[str], backup_dir: Path) -> dict[str, bool]:
        shutil.rmtree(backup_dir, ignore_errors=True)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backups: dict[str, bool] = {}
        for relative in files_touched:
            source = self.root / relative
            backups[relative] = source.exists()
            if source.exists():
                destination = backup_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        return backups

    def _restore_files(self, backups: dict[str, bool], backup_dir: Path) -> None:
        for relative, existed in backups.items():
            target = self.root / relative
            if existed:
                source = backup_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            elif target.exists():
                target.unlink()
        shutil.rmtree(backup_dir, ignore_errors=True)

    def export_plan(self, plan: OpenCodePlan, path: Path) -> None:
        path.write_text(json.dumps({
            "summary": plan.summary,
            "files_expected": plan.files_expected,
            "website_change_reason": plan.website_change_reason,
            "monetization_change_reason": plan.monetization_change_reason,
        }, indent=2) + "\n", encoding="utf-8")
