from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import shutil
import subprocess
from typing import Any

from generations.config import AppConfig, DEFAULT_MODEL
from generations.models import ExecutionTask, TaskResult
from generations.workspace import WorktreeManager


class OpenCodeAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = AppConfig.from_root(root)
        self.binary = Path(os.getenv("OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode")))
        self.model = os.getenv("GENERATIONS_OPENCODE_MODEL", f"ollama/{DEFAULT_MODEL}")
        self.worktrees = WorktreeManager(self.config)

    def run_parallel_tasks(self, loop_counter: int, theme: str, tasks: list[ExecutionTask], debug_dir: Path) -> list[TaskResult]:
        with ThreadPoolExecutor(max_workers=min(len(tasks), self.config.parallel_tasks)) as pool:
            futures = [pool.submit(self._run_task, loop_counter, theme, task, debug_dir) for task in tasks]
            return [future.result() for future in futures]

    def _run_task(self, loop_counter: int, theme: str, task: ExecutionTask, debug_dir: Path) -> TaskResult:
        worktree, branch = self.worktrees.create(loop_counter, task)
        try:
            task.status = "running"
            if self.config.test_mode or not self.binary.exists():
                changed_files = self._fallback_edit(worktree, task)
                return TaskResult(task.task_id, task.scope, task.objective, str(worktree.relative_to(self.root)), branch, changed_files, "merged" if changed_files else "no_change", None, None, None, None, "fallback edit")

            prompt = json.dumps(
                {
                    "task": task.objective,
                    "theme": theme,
                    "allowed_paths": task.allowed_paths,
                    "success_signal": task.success_signal,
                    "instruction": "Make one coherent diff only inside the allowed paths. Do not commit.",
                },
                sort_keys=True,
            )
            before = set(self._git_changed_files(worktree))
            completed = subprocess.run(
                [str(self.binary), "run", "--format", "json", "--dir", str(worktree), "--agent", self.config.opencode_agent, "--model", self.model, "--", prompt],
                cwd=worktree,
                env=self._env(),
                capture_output=True,
                text=True,
                check=False,
            )
            stdout_path = debug_dir / f"task-{task.task_id}.stdout.log"
            stderr_path = debug_dir / f"task-{task.task_id}.stderr.log"
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")
            after = set(self._git_changed_files(worktree))
            changed = sorted(after - before)
            session_id = self._latest_session_id()
            export = self._export_session(session_id) if session_id else None
            status = "merged" if changed else "no_change"
            return TaskResult(task.task_id, task.scope, task.objective, str(worktree.relative_to(self.root)), branch, changed, status, session_id, export, str(stdout_path.relative_to(self.root)), str(stderr_path.relative_to(self.root)), completed.stderr.strip() or completed.stdout.strip() or "task completed")
        finally:
            self.worktrees.remove(worktree, branch)

    def _fallback_edit(self, worktree: Path, task: ExecutionTask) -> list[str]:
        target_root = self._first_allowed_target(worktree, task.allowed_paths)
        target_root.mkdir(parents=True, exist_ok=True)
        if task.scope == "active_game":
            target = target_root / f"task_{task.task_id.lower()}_note.md"
            target.write_text(f"# Task {task.task_id}\n\n{task.objective}\n", encoding="utf-8")
        elif task.scope == "website":
            target = target_root / "loop_plan_note.md"
            target.write_text(f"Current website task: {task.objective}\n", encoding="utf-8")
        else:
            target = target_root / f"task_{task.task_id.lower()}_note.md"
            target.write_text(f"Task objective: {task.objective}\n", encoding="utf-8")
        return [str(target.relative_to(worktree))]

    def _first_allowed_target(self, root: Path, allowed_paths: list[str]) -> Path:
        for relative in allowed_paths:
            candidate = root / relative
            if "." not in candidate.name:
                return candidate
            return candidate.parent
        return root

    def _git_changed_files(self, cwd: Path) -> list[str]:
        completed = subprocess.run(["git", "status", "--short"], cwd=cwd, capture_output=True, text=True, check=False)
        changed: list[str] = []
        for line in completed.stdout.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                changed.append(parts[1].strip())
        return changed

    def _latest_session_id(self) -> str | None:
        if not self.binary.exists():
            return None
        completed = subprocess.run([str(self.binary), "session", "list"], cwd=self.root, env=self._env(), capture_output=True, text=True, check=False)
        for line in completed.stdout.splitlines():
            if line.startswith("ses_"):
                return line.split()[0]
        return None

    def _export_session(self, session_id: str) -> str | None:
        out = self.config.opencode_state_dir / f"{session_id}.json"
        completed = subprocess.run([str(self.binary), "export", session_id], cwd=self.root, env=self._env(), capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return None
        out.write_text(completed.stdout, encoding="utf-8")
        return str(out.relative_to(self.root))

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        return env

    def commit(self, message: str) -> str | None:
        subprocess.run(["git", "add", "."], cwd=self.root, check=False, capture_output=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.root, check=False, capture_output=True)
        if diff.returncode == 0:
            return self.head_commit()
        completed = subprocess.run(["git", "commit", "-m", message], cwd=self.root, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return None
        return self.head_commit()

    def head_commit(self) -> str | None:
        completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True, check=False)
        return completed.stdout.strip() if completed.returncode == 0 else None

    def push_current_branch(self) -> tuple[bool, str]:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=self.root, capture_output=True, text=True, check=False).stdout.strip()
        if not branch:
            return False, "No current branch."
        completed = subprocess.run(["git", "push", "origin", branch], cwd=self.root, capture_output=True, text=True, check=False)
        return completed.returncode == 0, (completed.stdout + completed.stderr).strip()
