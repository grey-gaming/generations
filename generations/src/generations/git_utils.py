from __future__ import annotations

from pathlib import Path
import subprocess


def ensure_git_identity(root: Path) -> None:
    email = _git_output(root, ["git", "config", "user.email"])
    if not email:
        subprocess.run(["git", "config", "user.email", "generations@local"], cwd=root, check=False)
    name = _git_output(root, ["git", "config", "user.name"])
    if not name:
        subprocess.run(["git", "config", "user.name", "Generations"], cwd=root, check=False)


def init_repo_if_needed(root: Path) -> None:
    if (root / ".git").exists():
        return
    subprocess.run(["git", "init"], cwd=root, check=False)


def _git_output(root: Path, command: list[str]) -> str:
    completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
    return completed.stdout.strip()
