from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from generations.adapters.opencode import OpenCodeAdapter
from generations.adapters.ollama_cloud import OllamaCloudAdapter
from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.models import BlockPlan, ExecutionTask, LongTermVisionRecord, LoopPlan, RetrospectiveRecord
from generations.planning.repo_grounding import build_repo_map, repo_map_summary, resolve_allowed_paths
from generations.planning.store import PlanningStore
from generations.state import now_iso, save_json

PILLARS = ["self", "game", "monetization_platform"]
_PATHLIKE_PATTERN = re.compile(r"(?:^|[\s`'\"(])(?:/?[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")
_ROOTLIKE_PATTERN = re.compile(r"\b(?:platform|website|memory|docs|ci|vision|planning|scripts|src|tests)/[A-Za-z0-9_.\-/]+\b")
_CANONICAL_ROOT_FRAGMENT_PATTERN = re.compile(r"\b(?:generations|games/active)/")


class Planner:
    def __init__(self, config: AppConfig, model: OllamaCloudAdapter, opencode: OpenCodeAdapter, journal: JournalStore, memory: MemoryStore) -> None:
        self.config = config
        self.model = model
        self.opencode = opencode
        self.journal = journal
        self.memory = memory
        self.store = PlanningStore(config.planning_dir)

    def needs_long_term_vision(self, loop_counter: int) -> bool:
        if loop_counter == 0:
            return True
        return loop_counter > 0 and loop_counter % 100 == 0

    def is_block_planning_loop(self, loop_counter: int) -> bool:
        return loop_counter == 1 or (loop_counter > 1 and loop_counter % 10 == 1)

    def current_vision(self) -> dict[str, Any] | None:
        return (self.memory.latest().get("long_term_vision") or {}).get("current")

    def current_block_plan(self) -> dict[str, Any] | None:
        return (self.memory.latest().get("block_planning") or {}).get("current")

    def latest_retrospective(self) -> dict[str, Any] | None:
        return (self.memory.latest().get("retrospectives") or {}).get("latest")

    def ensure_long_term_vision(self, seed: str, loop_counter: int) -> tuple[LongTermVisionRecord | None, dict[str, Any]]:
        memory = self.memory.latest()
        existing = (memory.get("long_term_vision") or {}).get("current")
        if existing and not self.needs_long_term_vision(loop_counter):
            return LongTermVisionRecord(**existing), {"provider": "memory", "fallback": None}
        current_version = int((memory.get("long_term_vision") or {}).get("current_version") or 0)
        entries = self.journal.tail(20)
        record, meta = self.model.plan_long_term_vision(seed, loop_counter, memory, entries, current_version=current_version)
        if record is None:
            return None, meta
        self._write_vision_files(record)
        updated = dict(memory)
        vision_state = dict(updated.get("long_term_vision") or {})
        history = list(vision_state.get("history") or [])
        history.append(record.as_dict())
        vision_state.update(
            {
                "current_version": record.version,
                "last_refined_loop": loop_counter,
                "current": record.as_dict(),
                "history": history[-10:],
            }
        )
        updated["long_term_vision"] = vision_state
        updated["pillars"] = {
            name: {
                "summary": pillar.get("summary", ""),
                "trajectory": (updated.get("pillars") or {}).get(name, {}).get("trajectory", "unclear"),
                "confidence": (updated.get("pillars") or {}).get(name, {}).get("confidence", 0.5),
                "current_state": pillar.get("good_end_state", ""),
                "biggest_risk": "; ".join(pillar.get("failure_modes") or ["No failure modes recorded."]),
            }
            for name, pillar in record.pillars.items()
        }
        self.memory.replace(updated, created_at=now_iso())
        save_json(self.config.current_long_term_vision_path, record.as_dict())
        self.store.write(loop_counter, {"entry_type": "long_term_vision", **record.as_dict(), "model_provider": meta})
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "vision" if loop_counter == 0 else "vision_refinement",
                "loop_counter": loop_counter,
                "long_term_vision": record.as_dict(),
                "model_provider": meta,
            }
        )
        return record, meta

    def ensure_block_material(self, seed: str, loop_counter: int) -> tuple[BlockPlan | None, RetrospectiveRecord | None, dict[str, Any]]:
        memory = self.memory.latest()
        if not self.is_block_planning_loop(loop_counter):
            current = (memory.get("block_planning") or {}).get("current")
            return (BlockPlan(**current), None, {"provider": "memory", "fallback": None}) if current else (None, None, {"provider": "memory", "fallback": "No block plan available."})

        vision = (memory.get("long_term_vision") or {}).get("current") or {}
        retrospective: RetrospectiveRecord | None = None
        retro_meta: dict[str, Any] = {"provider": "none", "fallback": None}
        if loop_counter > 1:
            prior_block = (memory.get("block_planning") or {}).get("current")
            if prior_block:
                block_entries = [entry for entry in self.journal.tail(50) if int(entry.get("loop_counter", -1)) in range(prior_block["execution_range"][0], prior_block["execution_range"][1] + 1)]
                retrospective, retro_meta = self.model.write_retrospective(seed, loop_counter, memory, prior_block, block_entries)
                if retrospective is not None:
                    self._persist_retrospective(memory, retrospective, retro_meta)
                    memory = self.memory.latest()

        if loop_counter == 1:
            plan, meta = self.model.plan_initial_self_block(seed, loop_counter, memory, vision)
        else:
            plan, meta = self.model.plan_block(seed, loop_counter, memory, vision, self.latest_retrospective(), block_id=self.block_id_for_planning_loop(loop_counter))
        if plan is None:
            meta["retrospective"] = retro_meta
            return None, retrospective, meta
        self._persist_block_plan(memory, plan, meta)
        return plan, retrospective, meta

    def block_id_for_planning_loop(self, planning_loop: int) -> int:
        return 1 + ((planning_loop - 1) // 10)

    def plan_execution_loop(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        block_plan: dict[str, Any],
        vision: dict[str, Any] | None,
    ) -> tuple[LoopPlan | None, dict[str, Any]]:
        repo_map = build_repo_map(self.config.root)
        raw_plan, aica_meta = self.opencode.plan_execution_loop(seed, loop_counter, memory, block_plan, vision, repo_map)
        if raw_plan is not None:
            if str(raw_plan.get("status") or "").strip().lower() == "rest_required":
                aica_meta["rest_required"] = raw_plan.get("reason") or "AICA planner requested rest."
                return None, aica_meta
            compiled = self._compile_execution_plan(raw_plan, loop_counter, block_plan, repo_map)
            aica_meta["repo_map_summary"] = repo_map_summary(repo_map)
            return compiled, aica_meta

        loop_plan, fallback_meta = self.model.plan_execution_loop(seed, loop_counter, memory, block_plan, vision)
        meta = {
            "provider": "planner",
            "fallback": aica_meta.get("fallback"),
            "aica": aica_meta,
            "ollama": fallback_meta,
            "repo_map_summary": repo_map_summary(repo_map),
        }
        if loop_plan is None:
            meta["rest_required"] = fallback_meta.get("rest_required")
            return None, meta
        return self._compile_execution_plan(loop_plan.as_dict(), loop_counter, block_plan, repo_map), meta

    def _persist_block_plan(self, memory: dict[str, Any], plan: BlockPlan, meta: dict[str, Any]) -> None:
        plan = self._sanitize_block_plan(plan)
        updated = dict(memory)
        block_state = dict(updated.get("block_planning") or {})
        history = list(block_state.get("history") or [])
        history.append(plan.as_dict())
        block_state["current"] = plan.as_dict()
        block_state["history"] = history[-20:]
        updated["block_planning"] = block_state
        updated["active_game"] = {
            **dict(updated.get("active_game") or {}),
            "status": "building" if plan.primary_pillar == "game" else updated.get("active_game", {}).get("status", "visioning"),
        }
        self.memory.replace(updated, created_at=now_iso())
        save_json(self.config.current_block_plan_path, plan.as_dict())
        self._write_block_plan_file(plan)
        self.store.write(plan.planning_loop, {"entry_type": "block_plan", **plan.as_dict(), "model_provider": meta})
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "block_planning",
                "loop_counter": plan.planning_loop,
                "block_plan": plan.as_dict(),
                "model_provider": meta,
            }
        )

    def _compile_execution_plan(
        self,
        raw_plan: dict[str, Any],
        loop_counter: int,
        block_plan: dict[str, Any],
        repo_map: dict[str, Any],
    ) -> LoopPlan:
        primary_pillar = str(raw_plan.get("primary_pillar") or block_plan["primary_pillar"])
        raw_tasks = list(raw_plan.get("tasks") or [])[:3]
        tasks: list[ExecutionTask] = []
        for index, raw_task in enumerate(raw_tasks, start=1):
            intent_label = self.model._normalize_intent_label(raw_task.get("intent_label") or raw_task.get("scope") or raw_task.get("working_on"))
            candidate_paths = [str(item) for item in (raw_task.get("candidate_paths") or raw_task.get("allowed_paths") or [])]
            route = self.model._infer_execution_route(
                intent_label=intent_label,
                allowed_paths=candidate_paths,
                objective=str(raw_task.get("objective") or ""),
                primary_pillar=primary_pillar,
            )
            allowed_paths = resolve_allowed_paths(
                self.config.root,
                intent_label,
                route,
                repo_map,
                candidate_paths,
            )
            tasks.append(
                ExecutionTask(
                    task_id=str(raw_task.get("task_id") or f"T{loop_counter:02d}-{index:02d}"),
                    intent_label=intent_label,
                    execution_route=route,
                    objective=str(raw_task.get("objective") or "Advance the active block with one coherent change."),
                    allowed_paths=allowed_paths,
                    success_signal=str(raw_task.get("success_signal") or "A coherent repository change lands."),
                    priority=_normalize_priority(raw_task.get("priority"), index),
                    support_reason=str(raw_task.get("support_reason") or "Supports the current block objective."),
                    pillar_alignment=self.model._normalize_pillar_alignment(raw_task.get("pillar_alignment"), route, primary_pillar),
                )
            )

        return LoopPlan(
            loop_counter=loop_counter,
            theme=str(raw_plan.get("theme") or f"Block {block_plan['block_id']} execution"),
            goal=str(raw_plan.get("goal") or f"Advance the {primary_pillar} pillar coherently inside the active block."),
            working_on=self.model._normalize_working_on(raw_plan.get("working_on")),
            primary_pillar=primary_pillar,
            block_id=int(raw_plan.get("block_id") or block_plan["block_id"]),
            planning_mode=False,
            block_plan_ref=int(block_plan["block_id"]),
            support_task_policy={"requires_justification": True},
            pillar_budget=_normalize_budget(raw_plan.get("pillar_budget"), primary_pillar),
            block_alignment=self.model._normalize_block_alignment(raw_plan.get("block_alignment"), tasks),
            drift_reason=self.model._normalize_drift_reason(raw_plan.get("drift_reason")),
            tasks=tasks,
            integration_policy=_normalize_integration_policy(raw_plan.get("integration_policy"), tasks),
            rationale=str(raw_plan.get("rationale") or "Execution loop aligns to the active block."),
        )

    def _sanitize_block_plan(self, plan: BlockPlan) -> BlockPlan:
        return BlockPlan(
            block_id=plan.block_id,
            planning_loop=plan.planning_loop,
            execution_range=plan.execution_range,
            primary_pillar=plan.primary_pillar,
            why_this_pillar_now=self._sanitize_text(plan.why_this_pillar_now),
            target_outcomes=self._sanitize_items(plan.target_outcomes),
            sub_goals=self._sanitize_items(plan.sub_goals),
            allowed_support_work=self._sanitize_items(plan.allowed_support_work),
            explicit_non_goals=self._sanitize_items(plan.explicit_non_goals),
            success_signals=self._sanitize_items(plan.success_signals),
            failure_signals=self._sanitize_items(plan.failure_signals),
            expected_artifacts=self._sanitize_items(plan.expected_artifacts),
            metrics_to_watch=self._sanitize_items(plan.metrics_to_watch),
            risks=self._sanitize_items(plan.risks),
            review_focus=self._sanitize_items(plan.review_focus),
        )

    def _sanitize_items(self, items: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in items:
            value = self._sanitize_text(item)
            if value and value not in cleaned:
                cleaned.append(value)
        return cleaned

    def _sanitize_text(self, text: str) -> str:
        value = " ".join(str(text).split()).strip()
        if not value:
            return value
        value = _ROOTLIKE_PATTERN.sub(lambda match: self._describe_path_fragment(match.group(0)), value)
        value = _PATHLIKE_PATTERN.sub(lambda match: self._describe_path_fragment(match.group(0).strip(" `\"'()")), value)
        value = _CANONICAL_ROOT_FRAGMENT_PATTERN.sub("", value)
        replacements = {
            "journey.html": "journey page template",
            "validation.py": "validation module",
            "state_schema.json": "memory schema definition",
            "block_001_plan.json": "block planning record",
            "platform_architecture.md": "platform architecture note",
            "loop_manager.py": "loop orchestration module",
            "journey_generator.py": "journey renderer",
            "loop_001.json": "loop state snapshot",
        }
        for raw, replacement in replacements.items():
            value = value.replace(raw, replacement)
        value = re.sub(r"\b(at|in|within|on)\s*/\b", "", value)
        value = re.sub(r"\s{2,}", " ", value).strip(" -:;,")
        if not value:
            return "Describe the capability or artifact without naming repository paths."
        return value

    def _describe_path_fragment(self, raw: str) -> str:
        candidate = raw.strip(" `\"'()")
        tail = candidate.split("/")[-1]
        if not tail:
            return "repository artifact"
        if "." in tail:
            stem = tail.rsplit(".", 1)[0]
            return stem.replace("_", " ")
        return tail.replace("_", " ")

    def _persist_retrospective(self, memory: dict[str, Any], retrospective: RetrospectiveRecord, meta: dict[str, Any]) -> None:
        updated = dict(memory)
        retro_state = dict(updated.get("retrospectives") or {})
        history = list(retro_state.get("history") or [])
        history.append(retrospective.as_dict())
        retro_state["latest"] = retrospective.as_dict()
        retro_state["history"] = history[-20:]
        updated["retrospectives"] = retro_state
        self.memory.replace(updated, created_at=now_iso())
        save_json(self.config.latest_retrospective_path, retrospective.as_dict())
        self._write_retrospective_file(retrospective)
        self.store.write(retrospective.retrospective_loop, {"entry_type": "retrospective", **retrospective.as_dict(), "model_provider": meta})
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "retrospective",
                "loop_counter": retrospective.retrospective_loop,
                "retrospective": retrospective.as_dict(),
                "model_provider": meta,
            }
        )

    def _write_vision_files(self, record: LongTermVisionRecord) -> None:
        vision_dir = self.config.generations_vision_dir
        vision_dir.mkdir(parents=True, exist_ok=True)
        for name, pillar in record.pillars.items():
            out = vision_dir / f"vision_v{record.version:03d}_{name}.md"
            out.write_text(
                "\n".join(
                    [
                        f"# {name.replace('_', ' ').title()} Vision",
                        "",
                        f"Version: {record.version}",
                        f"Refined at loop: {record.refined_at_loop}",
                        "",
                        f"## Purpose\n{pillar.get('purpose', '')}",
                        "",
                        f"## Good End State\n{pillar.get('good_end_state', '')}",
                        "",
                        "## Failure Modes",
                        *[f"- {item}" for item in pillar.get("failure_modes", [])],
                        "",
                        "## Relationships",
                        *[f"- {item}" for item in pillar.get("relationships", [])],
                        "",
                        "## Vision",
                        pillar.get("content", ""),
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        index_file = vision_dir / f"vision_index_v{record.version:03d}.md"
        index_file.write_text(
            "\n".join(
                [
                    "# Long-Term Vision Index",
                    "",
                    f"Version: {record.version}",
                    f"Refined at loop: {record.refined_at_loop}",
                    "",
                    record.index_summary,
                    "",
                    "## Pillars",
                    *[f"- {name}: {pillar.get('summary', '')}" for name, pillar in record.pillars.items()],
                ]
            ),
            encoding="utf-8",
        )

    def _write_block_plan_file(self, plan: BlockPlan) -> None:
        planning_dir = self.config.generations_planning_docs_dir
        planning_dir.mkdir(parents=True, exist_ok=True)
        out = planning_dir / f"block_{plan.block_id:03d}_plan.md"
        out.write_text(
            "\n".join(
                [
                    f"# Block {plan.block_id} Plan",
                    "",
                    f"Planning loop: {plan.planning_loop}",
                    f"Execution range: {plan.execution_range[0]}-{plan.execution_range[1]}",
                    f"Primary pillar: {plan.primary_pillar}",
                    "",
                    "## Why This Pillar Now",
                    plan.why_this_pillar_now,
                    "",
                    "## Target Outcomes",
                    *[f"- {item}" for item in plan.target_outcomes],
                    "",
                    "## Sub Goals",
                    *[f"- {item}" for item in plan.sub_goals],
                    "",
                    "## Allowed Support Work",
                    *[f"- {item}" for item in plan.allowed_support_work],
                    "",
                    "## Explicit Non Goals",
                    *[f"- {item}" for item in plan.explicit_non_goals],
                    "",
                    "## Success Signals",
                    *[f"- {item}" for item in plan.success_signals],
                    "",
                    "## Failure Signals",
                    *[f"- {item}" for item in plan.failure_signals],
                    "",
                    "## Expected Artifacts",
                    *[f"- {item}" for item in plan.expected_artifacts],
                    "",
                    "## Metrics To Watch",
                    *[f"- {item}" for item in plan.metrics_to_watch],
                    "",
                    "## Risks",
                    *[f"- {item}" for item in plan.risks],
                    "",
                    "## Review Focus",
                    *[f"- {item}" for item in plan.review_focus],
                ]
            ),
            encoding="utf-8",
        )

    def _write_retrospective_file(self, retrospective: RetrospectiveRecord) -> None:
        planning_dir = self.config.generations_planning_docs_dir
        planning_dir.mkdir(parents=True, exist_ok=True)
        out = planning_dir / f"block_{retrospective.block_id:03d}_retrospective.md"
        out.write_text(
            "\n".join(
                [
                    f"# Block {retrospective.block_id} Retrospective",
                    "",
                    f"Retrospective loop: {retrospective.retrospective_loop}",
                    f"Primary pillar: {retrospective.primary_pillar}",
                    f"Execution range: {retrospective.execution_range[0]}-{retrospective.execution_range[1]}",
                    "",
                    retrospective.summary,
                    "",
                    "## Wins",
                    *[f"- {item}" for item in retrospective.wins],
                    "",
                    "## Failures",
                    *[f"- {item}" for item in retrospective.failures],
                    "",
                    "## Stalls",
                    *[f"- {item}" for item in retrospective.stalls],
                    "",
                    "## Surprises",
                    *[f"- {item}" for item in retrospective.surprises],
                    "",
                    "## Carry Forward",
                    *[f"- {item}" for item in retrospective.carry_forward],
                    "",
                    "## Change Next Time",
                    *[f"- {item}" for item in retrospective.change_next_time],
                ]
            ),
            encoding="utf-8",
        )


def _normalize_budget(value: Any, primary_pillar: str) -> dict[str, float]:
    if isinstance(value, dict):
        normalized = {str(key): max(0.0, min(1.0, float(val))) for key, val in value.items()}
        if normalized:
            return normalized
    if primary_pillar == "self":
        return {"self": 0.7, "game": 0.15, "monetization_platform": 0.15}
    if primary_pillar == "game":
        return {"self": 0.2, "game": 0.65, "monetization_platform": 0.15}
    return {"self": 0.15, "game": 0.15, "monetization_platform": 0.7}


def _normalize_integration_policy(value: Any, tasks: list[ExecutionTask]) -> dict[str, Any]:
    if isinstance(value, dict):
        normalized = dict(value)
        if not isinstance(normalized.get("merge_order"), list):
            normalized["merge_order"] = [task.task_id for task in tasks]
        normalized.setdefault("allow_partial_success", True)
        return normalized
    if isinstance(value, str) and value.strip():
        return {
            "merge_order": [task.task_id for task in tasks],
            "allow_partial_success": True,
            "notes": value.strip(),
        }
    return {"merge_order": [task.task_id for task in tasks], "allow_partial_success": True}


def _normalize_priority(value: Any, default: int) -> int:
    if isinstance(value, int):
        return max(1, value)
    if isinstance(value, float):
        return max(1, int(value))

    text = str(value or "").strip().lower()
    if not text:
        return max(1, default)
    if text.isdigit():
        return max(1, int(text))

    normalized = text.replace("-", "_").replace(" ", "_")
    aliases = {
        "highest": 1,
        "critical": 1,
        "high": 1,
        "p1": 1,
        "medium": 2,
        "normal": 2,
        "default": 2,
        "p2": 2,
        "low": 3,
        "minor": 3,
        "p3": 3,
    }
    return aliases.get(normalized, max(1, default))
