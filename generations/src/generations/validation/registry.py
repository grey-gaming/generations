from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

from generations.models import ValidationResult


@dataclass(slots=True)
class ValidationPlan:
    fast: list[list[str]]
    targeted: list[list[str]]
    full: list[list[str]]


def build_validation_plan(root: Path, changed_paths: Iterable[str], loop_counter: int, test_mode: bool) -> ValidationPlan:
    if test_mode:
        return ValidationPlan(fast=[[sys.executable, "-m", "pytest", "generations/tests/test_journal.py"]], targeted=[], full=[])
    changed = list(changed_paths)
    fast = [
        [sys.executable, "-m", "pytest", "generations/tests/test_journal.py", "generations/tests/test_smoke.py", "games/hello_game/tests/test_hello_game.py"],
    ]
    targeted: list[list[str]] = []
    if any(path.startswith("games/active/") for path in changed):
        targeted.append([sys.executable, "-m", "pytest", "generations/tests/test_active_game.py"])
    if any(path.startswith("generations/src/generations/web/") for path in changed):
        targeted.append([sys.executable, "-m", "pytest", "generations/tests/test_web.py"])
    full: list[list[str]] = []
    if loop_counter % 5 == 0 or len(changed) > 4:
        full.append([sys.executable, "-m", "pytest", "generations/tests"])
    return ValidationPlan(fast=fast, targeted=targeted, full=full)
