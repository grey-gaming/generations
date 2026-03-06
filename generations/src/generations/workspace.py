from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from generations.config import AppConfig
from generations.models import ExecutionTask


class WorktreeManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.root = config.root
        self.base = self.root / ".worktrees"
        self.base.mkdir(parents=True, exist_ok=True)

    def create(self, loop_counter: int, task: ExecutionTask) -> tuple[Path, str]:
        path = self.base / f"loop-{loop_counter:04d}-{task.task_id}"
        branch = f"generations/loop-{loop_counter:04d}-{task.task_id.lower()}"
        shutil.rmtree(path, ignore_errors=True)
        subprocess.run(["git", "branch", "-D", branch], cwd=self.root, check=False, capture_output=True, text=True)
        subprocess.run(["git", "worktree", "add", "-b", branch, str(path), "HEAD"], cwd=self.root, check=False, capture_output=True, text=True)
        return path, branch

    def remove(self, path: Path, branch: str) -> None:
        subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=self.root, check=False, capture_output=True, text=True)
        subprocess.run(["git", "branch", "-D", branch], cwd=self.root, check=False, capture_output=True, text=True)
