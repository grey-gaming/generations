from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import shutil
import subprocess
from typing import Callable

from generations.config import AppConfig
from generations.config import DEFAULT_MODEL
from generations.models import OpenCodePlan, ValidationResult


@dataclass(slots=True)
class OpenCodeResult:
    plan: OpenCodePlan
    files_touched: list[str]
    validation: list[ValidationResult]
    commit_hash: str | None
    committed: bool
    rolled_back: bool
    opencode_session_id: str | None
    opencode_session_export: str | None
    opencode_changed_files: list[str]
    pushed: bool
    push_output: str


class OpenCodeAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = AppConfig.from_root(root)
        self.binary = Path(os.getenv("OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode")))

    def run_workflow(
        self,
        plan: OpenCodePlan,
        apply_fn: Callable[[], list[str]],
        verify_commands: list[list[str]],
        commit_message: str,
    ) -> OpenCodeResult:
        backup_dir = self.root / ".generations_tmp_backup"
        backups = self._snapshot_files(plan.files_expected, backup_dir)
        session_id, opencode_files = self._apply_via_opencode(plan, commit_message)
        files_touched = list(dict.fromkeys(opencode_files + apply_fn()))
        meaningful_files = self._meaningful_repo_files(files_touched)
        if not meaningful_files:
            self._restore_files(backups, backup_dir)
            export_path = self._export_session(session_id) if session_id else None
            validation = [
                ValidationResult(
                    success=False,
                    command="policy:meaningful-repo-edit",
                    output="No meaningful repository edit was produced outside state/ and site/.",
                )
            ]
            return OpenCodeResult(plan, files_touched, validation, None, False, True, session_id, export_path, opencode_files, False, "")
        validation = [self._run_command(cmd) for cmd in verify_commands]
        if not all(item.success for item in validation):
            self._restore_files(backups, backup_dir)
            export_path = self._export_session(session_id) if session_id else None
            return OpenCodeResult(plan, files_touched, validation, None, False, True, session_id, export_path, opencode_files, False, "")
        commit_hash = self._commit(commit_message)
        pushed, push_output = self._push_current_branch() if commit_hash else (False, "")
        shutil.rmtree(backup_dir, ignore_errors=True)
        export_path = self._export_session(session_id) if session_id else None
        return OpenCodeResult(plan, files_touched, validation, commit_hash, commit_hash is not None, False, session_id, export_path, opencode_files, pushed, push_output)

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
        path.write_text(json.dumps(plan.as_dict(), indent=2) + "\n", encoding="utf-8")

    def _apply_via_opencode(self, plan: OpenCodePlan, commit_message: str) -> tuple[str | None, list[str]]:
        if not self.binary.exists():
            return None, []
        before = set(self._list_sessions())
        before_diff = set(self._git_changed_files())
        attachments = self._prepare_session_files(plan, commit_message)
        prompt = json.dumps(
            {
                "task": "Apply one tiny coherent repository edit for Generations.",
                "plan": plan.as_dict(),
                "commit_message": commit_message,
                "cwd": str(self.root),
                "instruction": (
                    "Use the attached plan and git context to make a real file edit in this repository. "
                    "Only edit files listed in editable_files. Keep the change tiny, coherent, and reversible. "
                    "Do not commit. Do not touch generated state, caches, sqlite files, or logs. "
                    "Prefer the smallest change that advances the stated workstream and capability target."
                ),
            },
            sort_keys=True,
        )
        command = [
            str(self.binary),
            "run",
            "--format",
            "json",
            "--title",
            f"Generations workflow: {plan.summary[:48]}",
            "--dir",
            str(self.root),
            "--model",
            f"ollama/{DEFAULT_MODEL}",
        ]
        for attachment in attachments:
            command.extend(["--file", str(attachment)])
        command.append(prompt)
        completed = subprocess.run(command, cwd=self.root, env=self._env(), check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            return None, []
        after = self._list_sessions()
        session_id = None
        for session_id in after:
            if session_id not in before:
                break
        if session_id is None:
            session_id = after[0] if after else None
        after_diff = set(self._git_changed_files())
        opencode_files = sorted(after_diff - before_diff)
        return session_id, opencode_files

    def _prepare_session_files(self, plan: OpenCodePlan, commit_message: str) -> list[Path]:
        input_dir = self.config.opencode_state_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        plan_path = input_dir / "workflow_plan.json"
        git_path = input_dir / "git_context.json"
        note_path = input_dir / "workflow_note.txt"

        plan_path.write_text(json.dumps(plan.as_dict(), indent=2) + "\n", encoding="utf-8")
        git_path.write_text(json.dumps(self._git_context(commit_message), indent=2) + "\n", encoding="utf-8")
        note_path.write_text(
            "Generations OpenCode session bootstrap.\n"
            "Attached files provide the planned workflow and current git context.\n"
            "Use them for repository-aware editing within the allowed editable files only.\n",
            encoding="utf-8",
        )
        attachments = [plan_path, git_path, note_path]
        for relative in plan.editable_files:
            candidate = self.root / relative
            if candidate.exists() and candidate.is_file():
                attachments.append(candidate)
        return attachments

    def _git_context(self, commit_message: str) -> dict[str, object]:
        return {
            "head": self._git_output(["git", "rev-parse", "HEAD"]),
            "branch": self._git_output(["git", "branch", "--show-current"]),
            "status_short": self._git_output(["git", "status", "--short"]),
            "recent_commits": self._git_output(["git", "log", "--oneline", "-n", "5"]),
            "planned_commit_message": commit_message,
        }

    def _git_output(self, command: list[str]) -> str:
        completed = subprocess.run(
            command,
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def _git_changed_files(self) -> list[str]:
        output = self._git_output(["git", "status", "--short"])
        changed: list[str] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            changed.append(line[3:])
        return changed

    def _meaningful_repo_files(self, files: list[str]) -> list[str]:
        return [
            path for path in files
            if path
            and not path.startswith("state/")
            and not path.startswith("site/")
            and "__pycache__" not in path
            and not path.endswith(".pyc")
        ]

    def _push_current_branch(self) -> tuple[bool, str]:
        branch = self._git_output(["git", "branch", "--show-current"])
        if not branch:
            return False, "No current branch to push."
        completed = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout + completed.stderr).strip()
        return completed.returncode == 0, output

    def _list_sessions(self) -> list[str]:
        if not self.binary.exists():
            return []
        completed = subprocess.run(
            [str(self.binary), "session", "list"],
            cwd=self.root,
            env=self._env(),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return []
        session_ids: list[str] = []
        for line in completed.stdout.splitlines():
            if not line.startswith("ses_"):
                continue
            session_ids.append(line.split()[0])
        return session_ids

    def _export_session(self, session_id: str) -> str | None:
        export_dir = self.config.opencode_state_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        out_path = export_dir / f"{session_id}.json"
        completed = subprocess.run(
            [str(self.binary), "export", session_id],
            cwd=self.root,
            env=self._env(),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        lines = completed.stdout.splitlines()
        json_start = next((index for index, line in enumerate(lines) if line.strip().startswith("{")), None)
        if json_start is None:
            return None
        out_path.write_text("\n".join(lines[json_start:]) + "\n", encoding="utf-8")
        return str(out_path.relative_to(self.root))

    def _env(self) -> dict[str, str]:
        base = self.config.opencode_state_dir
        data_dir = base / "data"
        config_dir = base / "config"
        state_dir = base / "state"
        cache_dir = base / "cache"
        for item in (data_dir, config_dir, state_dir, cache_dir):
            item.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "XDG_DATA_HOME": str(data_dir),
                "XDG_CONFIG_HOME": str(config_dir),
                "XDG_STATE_HOME": str(state_dir),
                "XDG_CACHE_HOME": str(cache_dir),
            }
        )
        self._write_config(config_dir)
        return env

    def _write_config(self, config_dir: Path) -> None:
        opencode_dir = config_dir / "opencode"
        opencode_dir.mkdir(parents=True, exist_ok=True)
        config_path = opencode_dir / "opencode.json"
        config = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ollama": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Ollama",
                    "options": {
                        "baseURL": os.getenv("OLLAMA_OPENCODE_BASE_URL", "http://localhost:11434/v1"),
                    },
                    "models": {
                        DEFAULT_MODEL: {
                            "name": DEFAULT_MODEL,
                        }
                    },
                }
            },
        }
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
