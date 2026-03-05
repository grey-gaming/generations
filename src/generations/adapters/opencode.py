from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import shutil
import subprocess
from typing import Callable

from generations.config import AppConfig
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
        session_id = self._start_session(plan, commit_message)
        backup_dir = self.root / ".generations_tmp_backup"
        backups = self._snapshot_files(plan.files_expected, backup_dir)
        files_touched = apply_fn()
        validation = [self._run_command(cmd) for cmd in verify_commands]
        if not all(item.success for item in validation):
            self._restore_files(backups, backup_dir)
            export_path = self._export_session(session_id) if session_id else None
            return OpenCodeResult(plan, files_touched, validation, None, False, True, session_id, export_path)
        commit_hash = self._commit(commit_message)
        shutil.rmtree(backup_dir, ignore_errors=True)
        export_path = self._export_session(session_id) if session_id else None
        return OpenCodeResult(plan, files_touched, validation, commit_hash, commit_hash is not None, False, session_id, export_path)

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

    def _start_session(self, plan: OpenCodePlan, commit_message: str) -> str | None:
        if not self.binary.exists():
            return None
        before = set(self._list_sessions())
        command = [
            str(self.binary),
            "run",
            "--format",
            "json",
            "--title",
            f"Generations workflow: {plan.summary[:48]}",
            "--command",
            "/bin/true",
            json.dumps(
                {
                    "plan": plan.as_dict(),
                    "commit_message": commit_message,
                    "cwd": str(self.root),
                },
                sort_keys=True,
            ),
        ]
        subprocess.run(command, cwd=self.root, env=self._env(), check=False, capture_output=True, text=True)
        after = self._list_sessions()
        for session_id in after:
            if session_id not in before:
                return session_id
        return after[0] if after else None

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
        return env
