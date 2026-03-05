from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Criteria:
    version: int
    summary: str
    ship_rules: list[str]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "summary": self.summary,
            "ship_rules": self.ship_rules,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ValidationResult:
    success: bool
    command: str
    output: str

    def as_dict(self) -> dict[str, Any]:
        return {"success": self.success, "command": self.command, "output": self.output}


@dataclass(slots=True)
class OpenCodePlan:
    summary: str
    files_expected: list[str]
    website_change_reason: str
    monetization_change_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "files_expected": self.files_expected,
            "website_change_reason": self.website_change_reason,
            "monetization_change_reason": self.monetization_change_reason,
        }


@dataclass(slots=True)
class StepProposal:
    description: str
    rationale: str
    target_files: list[str]
    website_change: bool
    website_reason: str
    monetization_change: bool
    monetization_reason: str
    heuristics_updates: list[str]
