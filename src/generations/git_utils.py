from __future__ import annotations

from pathlib import Path
import subprocess


def ensure_git_identity(root: Path) -> None:
    email = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True, text=True, check=False)
    name = subprocess.run(["git", "config", "user.name"], cwd=root, capture_output=True, text=True, check=False)
    if email.returncode != 0 or not email.stdout.strip():
        subprocess.run(["git", "config", "user.email", "generations@local"], cwd=root, check=False, capture_output=True)
    if name.returncode != 0 or not name.stdout.strip():
        subprocess.run(["git", "config", "user.name", "Generations"], cwd=root, check=False, capture_output=True)
