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
        self._workspace_config_home = self.config.opencode_state_dir / "config"
        self._workspace_config_path = self._workspace_config_home / "opencode" / "opencode.json"
        self._ensure_workspace_config()

    def run_parallel_tasks(self, loop_counter: int, theme: str, tasks: list[ExecutionTask], debug_dir: Path) -> list[TaskResult]:
        with ThreadPoolExecutor(max_workers=min(len(tasks), self.config.parallel_tasks)) as pool:
            futures = [pool.submit(self._run_task, loop_counter, theme, task, debug_dir) for task in tasks]
            return [future.result() for future in futures]

    def plan_execution_loop(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        block_plan: dict[str, Any],
        vision: dict[str, Any] | None,
        repo_map: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        meta: dict[str, Any] = {
            "provider": "opencode",
            "model": self.model,
            "fallback": None,
            "repo_map": repo_map,
        }
        if self.config.test_mode or not self.binary.exists():
            meta["fallback"] = "OpenCode planner unavailable."
            return None, meta

        worktree, branch = self._create_planning_worktree(loop_counter)
        try:
            prompt = json.dumps(
                {
                    "role": "Generations planning agent",
                    "seed": seed,
                    "loop_counter": loop_counter,
                    "block_plan": block_plan,
                    "vision": vision,
                    "memory": {
                        "evaluation_metrics": (memory.get("evaluation_metrics") or {}).get("rolling_average") or {},
                        "execution_history": memory.get("execution_history") or {},
                        "outcomes": memory.get("outcomes") or {},
                    },
                    "repo_map": repo_map,
                    "instruction": (
                        "Inspect the repository and propose one execution loop as JSON only. "
                        "Do not edit files. Do not invent repository roots. "
                        "Return keys: status, theme, goal, working_on, primary_pillar, block_id, pillar_budget, "
                        "block_alignment, drift_reason, tasks, integration_policy, rationale. "
                        "Each task must include task_id, intent_label, objective, candidate_paths, success_signal, "
                        "priority, support_reason, pillar_alignment, repo_evidence. "
                        "candidate_paths must only reference paths you verified in the repo map or their existing parents. "
                        "If no valid plan is available, return status=rest_required with reason."
                    ),
                },
                sort_keys=True,
            )
            completed = subprocess.run(
                [str(self.binary), "run", "--format", "json", "--dir", str(worktree), "--agent", self.config.opencode_agent, "--model", self.model, "--", prompt],
                cwd=worktree,
                env=self._env(),
                capture_output=True,
                text=True,
                check=False,
            )
            stdout_text = self._extract_text_from_json_stream(completed.stdout)
            if not stdout_text:
                session_id = self._latest_session_id()
                if session_id:
                    export = self._export_session(session_id)
                    stdout_text = self._extract_text_from_session_export(export) if export else ""
            if not stdout_text:
                meta["fallback"] = "OpenCode planner produced no text response."
                return None, meta
            parsed = self._parse_json_text(stdout_text)
            if not isinstance(parsed, dict):
                meta["fallback"] = "OpenCode planner response was not a JSON object."
                return None, meta
            return parsed, meta
        except Exception as exc:
            meta["fallback"] = f"{type(exc).__name__}: {exc}"
            return None, meta
        finally:
            self._remove_planning_worktree(worktree, branch)

    def _run_task(self, loop_counter: int, theme: str, task: ExecutionTask, debug_dir: Path) -> TaskResult:
        worktree, branch = self.worktrees.create(loop_counter, task)
        task.status = "running"
        if self.config.test_mode or not self.binary.exists():
            changed_files = self._fallback_edit(worktree, task)
            return TaskResult(task.task_id, task.intent_label, task.execution_route, task.objective, task.allowed_paths, str(worktree.relative_to(self.root)), branch, changed_files, "merged" if changed_files else "no_change", None, None, None, None, "fallback edit")

        prompt = json.dumps(
            {
                "role": "Generations execution agent",
                "task": task.objective,
                "intent_label": task.intent_label,
                "execution_route": task.execution_route,
                "theme": theme,
                "allowed_paths": task.allowed_paths,
                "success_signal": task.success_signal,
                "support_reason": task.support_reason,
                "instruction": (
                    "You are operating inside a disposable git worktree. "
                    "Edit the files directly in this worktree. "
                    "Stay strictly inside the allowed_paths. "
                    "Prefer concrete code, test, design, or website edits over commentary. "
                    "Make the smallest coherent change that satisfies the task and success_signal. "
                    "Do not commit, do not create unrelated files, and do not explain what you would do instead of doing it."
                ),
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
        return TaskResult(task.task_id, task.intent_label, task.execution_route, task.objective, task.allowed_paths, str(worktree.relative_to(self.root)), branch, changed, status, session_id, export, str(stdout_path.relative_to(self.root)), str(stderr_path.relative_to(self.root)), completed.stderr.strip() or completed.stdout.strip() or "task completed")

    def cleanup_task_results(self, results: list[TaskResult]) -> None:
        for result in results:
            worktree = self.root / result.worktree
            self.worktrees.remove(worktree, result.branch)

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
                relative = parts[1].strip()
                path = cwd / relative
                if path.is_dir():
                    changed.extend(
                        str(child.relative_to(cwd))
                        for child in sorted(path.rglob("*"))
                        if child.is_file()
                    )
                else:
                    changed.append(relative)
        return sorted(set(changed))

    def _create_planning_worktree(self, loop_counter: int) -> tuple[Path, str]:
        path = self.worktrees.base / f"planner-{loop_counter:04d}"
        branch = f"generations/planner-{loop_counter:04d}"
        shutil.rmtree(path, ignore_errors=True)
        subprocess.run(["git", "branch", "-D", branch], cwd=self.root, check=False, capture_output=True, text=True)
        subprocess.run(["git", "worktree", "add", "-b", branch, str(path), "HEAD"], cwd=self.root, check=False, capture_output=True, text=True)
        return path, branch

    def _remove_planning_worktree(self, path: Path, branch: str) -> None:
        subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=self.root, check=False, capture_output=True, text=True)
        subprocess.run(["git", "branch", "-D", branch], cwd=self.root, check=False, capture_output=True, text=True)

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
        env["XDG_CONFIG_HOME"] = str(self._workspace_config_home)
        return env

    def _ensure_workspace_config(self) -> None:
        self._workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
        if self._workspace_config_path.exists():
            try:
                config = json.loads(self._workspace_config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}
        config.setdefault("$schema", "https://opencode.ai/config.json")
        provider = config.setdefault("provider", {})
        ollama = provider.setdefault("ollama", {})
        ollama["npm"] = "@ai-sdk/openai-compatible"
        ollama["name"] = "Local Ollama"
        options = ollama.setdefault("options", {})
        base = os.getenv("OLLAMA_OPENCODE_BASE_URL") or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
        if not base.endswith("/v1"):
            base = base.rstrip("/") + "/v1"
        options["baseURL"] = base
        models = ollama.setdefault("models", {})
        model_name = self.model.split("/", 1)[1] if self.model.startswith("ollama/") else self.model
        models[model_name] = {"name": f"Ollama {model_name}"}
        self._workspace_config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    def _extract_text_from_json_stream(self, payload: str) -> str:
        texts: list[str] = []
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            part = event.get("part") or {}
            if event.get("type") == "text" and isinstance(part.get("text"), str):
                texts.append(str(part["text"]))
        return texts[-1] if texts else ""

    def _extract_text_from_session_export(self, export_path: str | None) -> str:
        if not export_path:
            return ""
        path = self.root / export_path
        if not path.exists():
            return ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        texts: list[str] = []
        for message in payload.get("messages") or []:
            if ((message.get("info") or {}).get("role")) != "assistant":
                continue
            for part in message.get("parts") or []:
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    texts.append(str(part["text"]))
        return texts[-1] if texts else ""

    def _parse_json_text(self, text: str) -> dict[str, Any] | list[Any] | None:
        candidate = text.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
        return json.loads(candidate)

    def commit(self, message: str) -> str | None:
        subprocess.run(["git", "add", "."], cwd=self.root, check=False, capture_output=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.root, check=False, capture_output=True)
        if diff.returncode == 0:
            return None
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
