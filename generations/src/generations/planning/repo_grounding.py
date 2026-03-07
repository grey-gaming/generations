from __future__ import annotations

from pathlib import Path
from typing import Any

KNOWN_ROOTS = (
    "generations/src/generations",
    "generations/src/generations/web",
    "generations/src/generations/web/templates",
    "generations/memory",
    "generations/tests",
    "generations/tools",
    "generations/validation",
    "generations/core",
    "generations/vision",
    "generations/planning_docs",
    "site",
    "games/active/src",
    "games/active/tests",
    "games/active/design",
)

ROUTE_DEFAULTS: dict[str, tuple[str, ...]] = {
    "platform": (
        "generations/src/generations",
        "generations/memory",
        "generations/tools",
        "generations/validation",
        "generations/core",
        "generations/tests",
    ),
    "website": (
        "generations/src/generations/web",
        "generations/src/generations/web/templates",
        "site",
    ),
    "active_game": (
        "games/active/src",
        "games/active/tests",
        "games/active/design",
    ),
    "monetization_platform": (
        "generations/src/generations/web",
        "generations/src/generations/web/templates",
        "site",
        "generations/tests",
    ),
    "cross_cutting": (
        "generations/src/generations",
        "generations/tests",
        "games/active/src",
        "games/active/tests",
        "games/active/design",
        "site",
    ),
}

INTENT_PATH_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("memory_schema", "state_schema", "persistence", "data_architecture", "data_schema"), ("generations/memory", "generations/core", "generations/tests")),
    (("validation", "ci", "commit_hook", "validator"), ("generations/validation", "generations/tools", "generations/tests", "generations/src/generations")),
    (("journey_page", "journey", "observability", "public_log"), ("generations/src/generations/web", "site")),
    (("planner", "block_plan", "planning"), ("generations/src/generations", "generations/tests", "generations/planning_docs")),
    (("simulation", "economy", "cargo", "route", "station", "gameplay"), ("games/active/src", "games/active/tests", "games/active/design")),
    (("support", "monetization", "pricing", "commercial"), ("generations/src/generations/web", "site", "generations/tests")),
)


def build_repo_map(root: Path) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    existing_roots: list[str] = []
    for relative in KNOWN_ROOTS:
        path = root / relative
        if not path.exists():
            continue
        existing_roots.append(relative)
        samples = _sample_entries(path, root)
        roots.append(
            {
                "root": relative,
                "kind": "dir" if path.is_dir() else "file",
                "sample_entries": samples,
            }
        )
    return {
        "valid_roots": existing_roots,
        "roots": roots,
    }


def resolve_allowed_paths(
    root: Path,
    intent_label: str,
    execution_route: str,
    repo_map: dict[str, Any],
    candidate_paths: list[str] | None = None,
) -> list[str]:
    valid_roots = tuple(repo_map.get("valid_roots") or [])
    cleaned: list[str] = []
    for raw in candidate_paths or []:
        normalized = normalize_candidate_path(root, str(raw), valid_roots)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)

    for default in _intent_defaults(intent_label, execution_route):
        normalized = normalize_candidate_path(root, default, valid_roots)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def normalize_candidate_path(root: Path, raw_path: str, valid_roots: tuple[str, ...] | list[str]) -> str | None:
    candidate = str(raw_path or "").strip().replace("\\", "/")
    if not candidate:
        return None
    if candidate.startswith("./"):
        candidate = candidate[2:]
    candidate = candidate.rstrip("/")
    if not candidate:
        return None

    matching_root = next((known for known in valid_roots if candidate == known or candidate.startswith(f"{known}/")), None)
    if matching_root is None:
        return None

    full = root / candidate
    if full.exists():
        return candidate
    if full.parent.exists():
        return candidate
    return matching_root


def repo_map_summary(repo_map: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in repo_map.get("roots") or []:
        samples = ", ".join(item.get("sample_entries") or [])
        sample_text = f" sample=[{samples}]" if samples else ""
        parts.append(f"{item['root']}{sample_text}")
    return "\n".join(parts)


def _intent_defaults(intent_label: str, execution_route: str) -> tuple[str, ...]:
    label = intent_label.lower()
    for keywords, defaults in INTENT_PATH_HINTS:
        if any(keyword in label for keyword in keywords):
            return defaults
    return ROUTE_DEFAULTS.get(execution_route, ROUTE_DEFAULTS["platform"])


def _sample_entries(path: Path, root: Path) -> list[str]:
    if path.is_file():
        return [str(path.relative_to(root))]
    samples: list[str] = []
    for entry in sorted(path.rglob("*")):
        if entry.is_file():
            samples.append(str(entry.relative_to(root)))
        if len(samples) >= 5:
            break
    return samples
