from __future__ import annotations

import hashlib
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .adapters.ollama_cloud import OllamaCloudAdapter
from .adapters.opencode import OpenCodeAdapter
from .config import AppConfig
from .evaluator import Evaluator
from .integrator import Integrator
from .journal.store import JournalStore
from .memory.store import MemoryStore
from .planner import Planner
from .state import load_runtime, now_iso, save_current_loop_plan, save_json, save_runtime
from .tui import TUI
from .validation.registry import build_validation_plan
from .web.exporter import export_site


class Runner:
    def __init__(self, root: Path, seed: str, *, debug: bool = False, parallel_tasks: int | None = None) -> None:
        self.root = root
        self.seed = seed
        self.config = AppConfig.from_root(root, debug=debug)
        if parallel_tasks is not None:
            self.config.parallel_tasks = parallel_tasks
        self.journal = JournalStore(self.config.journal_path)
        self.memory = MemoryStore(self.config.memory_path)
        self.ollama = OllamaCloudAdapter()
        self.opencode = OpenCodeAdapter(root)
        self.integrator = Integrator(self.config)
        self.planner = Planner(self.config, self.ollama, self.journal, self.memory)
        self.evaluator = Evaluator()
        self.tui = TUI(debug=self.config.debug)
        self._shutdown = threading.Event()
        self._install_signal_handlers()

    def _install_signal_handlers(self) -> None:
        def _handle_interrupt(signum: int, frame: Any) -> None:
            self._shutdown.set()
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _handle_interrupt)
        signal.signal(signal.SIGTERM, _handle_interrupt)

    def run(self) -> None:
        runtime = load_runtime(self.config.runtime_path)
        save_runtime(self.config.runtime_path, runtime)
        self.tui.log_run_header(self._seed_hash(), int(runtime.get("loop_count", 0)), int(runtime.get("current_criteria_version", 1)), self.config.parallel_tasks)
        try:
            while not self._shutdown.is_set():
                runtime = load_runtime(self.config.runtime_path)
                if self.config.pause_flag.exists():
                    time.sleep(1)
                    continue
                if self.config.operational_max_loops is not None and int(runtime.get("loop_count", 0)) >= self.config.operational_max_loops:
                    self._write_shutdown(runtime, "Operational max loop limit reached.")
                    break
                self._run_single_loop(runtime)
                if self.config.test_mode:
                    break
        except KeyboardInterrupt:
            self._shutdown.set()
        if self._shutdown.is_set():
            self._write_shutdown(load_runtime(self.config.runtime_path), "Graceful shutdown requested by operator.")

    def _run_single_loop(self, runtime: dict[str, Any]) -> None:
        loop_counter = int(runtime.get("loop_count", 0))
        self._ensure_seed_baseline(loop_counter)

        if self.planner.needs_long_term_vision(loop_counter):
            self._run_vision_loop(runtime, loop_counter)
            return
        if self.planner.is_block_planning_loop(loop_counter):
            self._run_block_planning_loop(runtime, loop_counter)
            return
        self._run_execution_loop(runtime, loop_counter)

    def _run_vision_loop(self, runtime: dict[str, Any], loop_counter: int) -> None:
        memory = self.memory.latest()
        record, meta = self.planner.ensure_long_term_vision(self.seed, loop_counter)
        if record is None:
            self._record_rest_cycle(runtime, loop_counter, meta.get("fallback") or "No long-term vision could be produced.", meta)
            return
        current_loop_plan = {
            "loop_counter": loop_counter,
            "theme": "Long-term vision",
            "goal": "Define or refine the long-term purpose of the self, game, and monetization pillars.",
            "primary_pillar": "self",
            "block_id": 0,
            "tasks": [],
            "integration_status": "committed",
            "validation_status": "pending",
            "updated_at": now_iso(),
        }
        save_current_loop_plan(self.config.current_loop_plan_path, current_loop_plan)
        self.memory.update_current_loop_plan(current_loop_plan)
        changed = self._tracked_changes()
        validation = self._run_validation(changed, loop_counter)
        commit_hash, pushed = self._commit_if_valid(validation, f"loop {loop_counter}: define long-term vision")
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "loop",
                "loop_counter": loop_counter,
                "seed_hash": self._seed_hash(),
                "proposal": {"theme": "Long-term vision", "goal": current_loop_plan["goal"]},
                "vision": record.as_dict(),
                "validation": [item.as_dict() for item in validation],
                "provider": {"vision": meta},
                "diary": {
                    "title": f"Loop {loop_counter} long-term vision",
                    "mood": "visionary",
                    "entry": "I wrote down the longer arc so the future blocks can be judged against something more durable than momentum.",
                    "hopes": ["Use this vision to keep the next hundred loops coherent."],
                    "worries": ["A vision is only useful if later blocks remain accountable to it."],
                    "lessons": ["Long-term direction needs explicit words on disk."],
                    "next_desire": "Translate the vision into a concrete self-focused block.",
                },
            }
        )
        self._finalize_loop(runtime, loop_counter, commit_hash, validation, "continue")

    def _run_block_planning_loop(self, runtime: dict[str, Any], loop_counter: int) -> None:
        plan, retrospective, meta = self.planner.ensure_block_material(self.seed, loop_counter)
        if plan is None:
            self._record_rest_cycle(runtime, loop_counter, meta.get("fallback") or "No valid block plan was available.", meta)
            return
        current_loop_plan = {
            "loop_counter": loop_counter,
            "theme": f"Block {plan.block_id} planning",
            "goal": f"Plan the next 9-loop block around the {plan.primary_pillar} pillar.",
            "primary_pillar": plan.primary_pillar,
            "block_id": plan.block_id,
            "tasks": [],
            "integration_status": "committed",
            "validation_status": "pending",
            "updated_at": now_iso(),
        }
        save_current_loop_plan(self.config.current_loop_plan_path, current_loop_plan)
        self.memory.update_current_loop_plan(current_loop_plan)
        changed = self._tracked_changes()
        validation = self._run_validation(changed, loop_counter)
        commit_hash, pushed = self._commit_if_valid(validation, f"loop {loop_counter}: plan block {plan.block_id}")
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "loop",
                "loop_counter": loop_counter,
                "seed_hash": self._seed_hash(),
                "proposal": {
                    "theme": current_loop_plan["theme"],
                    "goal": current_loop_plan["goal"],
                    "primary_pillar": plan.primary_pillar,
                    "block_id": plan.block_id,
                },
                "block_plan": plan.as_dict(),
                "retrospective": retrospective.as_dict() if retrospective else None,
                "validation": [item.as_dict() for item in validation],
                "provider": {"block_plan": meta},
                "diary": {
                    "title": f"Loop {loop_counter} block planning",
                    "mood": "deliberate",
                    "entry": f"I set the direction for block {plan.block_id} and tied the next nine loops to the {plan.primary_pillar} pillar.",
                    "hopes": [f"Keep block {plan.block_id} coherent from loop {plan.execution_range[0]} onward."],
                    "worries": ["A block can still drift if each execution loop forgets why the pillar was chosen."],
                    "lessons": ["Retrospective plus plan is more useful than local improvisation."],
                    "next_desire": "Make the first execution loop of the new block feel obviously in-scope.",
                },
            }
        )
        self._finalize_loop(runtime, loop_counter, commit_hash, validation, "continue")

    def _run_execution_loop(self, runtime: dict[str, Any], loop_counter: int) -> None:
        memory = self.memory.latest()
        block_plan = (memory.get("block_planning") or {}).get("current")
        vision = (memory.get("long_term_vision") or {}).get("current")
        if not block_plan:
            self._record_rest_cycle(runtime, loop_counter, "No active block plan is available for execution.", {"provider": "runner", "fallback": None})
            return
        loop_plan, planner_meta = self.ollama.plan_execution_loop(self.seed, loop_counter, memory, block_plan, vision)
        if loop_plan is None:
            self._record_rest_cycle(runtime, loop_counter, planner_meta.get("rest_required") or planner_meta.get("fallback") or "Planner requested neutral rest.", planner_meta)
            return

        debug_dir = self.config.runs_dir / f"loop-{loop_counter:04d}"
        debug_dir.mkdir(parents=True, exist_ok=True)
        self.tui.write_debug_json(debug_dir / "planner.json", {"loop_plan": loop_plan.as_dict(), "provider": planner_meta})

        current_loop_plan = {
            "loop_counter": loop_counter,
            "theme": loop_plan.theme,
            "goal": loop_plan.goal,
            "primary_pillar": loop_plan.primary_pillar,
            "block_id": loop_plan.block_id,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "scope": task.scope,
                    "objective": task.objective,
                    "status": "planned",
                    "success_signal": task.success_signal,
                    "support_reason": task.support_reason,
                }
                for task in loop_plan.tasks
            ],
            "integration_status": "pending",
            "validation_status": "pending",
            "updated_at": now_iso(),
        }
        save_current_loop_plan(self.config.current_loop_plan_path, current_loop_plan)
        self.memory.update_current_loop_plan(current_loop_plan)
        self.tui.log_loop_plan(loop_plan)

        task_results = self.opencode.run_parallel_tasks(loop_counter, loop_plan.theme, loop_plan.tasks[: self.config.parallel_tasks], debug_dir)
        current_loop_plan["tasks"] = [
            {
                "task_id": result.task_id,
                "scope": result.scope,
                "objective": result.objective,
                "status": result.status,
                "changed_files": result.changed_files,
                "summary": result.summary,
            }
            for result in task_results
        ]
        save_current_loop_plan(self.config.current_loop_plan_path, current_loop_plan)
        self.memory.update_current_loop_plan(current_loop_plan)
        for result in task_results:
            self.tui.log_task_result(result)
            self.tui.write_debug_json(debug_dir / f"task-{result.task_id}.json", result.as_dict())

        try:
            integration = self.integrator.integrate(
                loop_counter,
                task_results,
                f"loop {loop_counter}: {loop_plan.theme}",
                self.opencode.commit,
                self.opencode.push_current_branch,
            )
        finally:
            self.opencode.cleanup_task_results(task_results)
        validation_passed = bool(integration.validation) and all(item.success for item in integration.validation)
        current_loop_plan["integration_status"] = "committed" if integration.commit_hash else "stalled"
        current_loop_plan["validation_status"] = "passed" if validation_passed else "failed"
        current_loop_plan["updated_at"] = now_iso()
        save_current_loop_plan(self.config.current_loop_plan_path, current_loop_plan)
        self.memory.update_current_loop_plan(current_loop_plan)

        metrics = self.evaluator.score_loop(loop_plan, integration)
        self.tui.log_integration(integration, metrics)
        self.tui.write_debug_json(debug_dir / "integration.json", integration.as_dict())
        self.tui.write_debug_json(debug_dir / "validation.json", {"validation": [item.as_dict() for item in integration.validation], "metrics": metrics})

        updated_memory = self.evaluator.update_memory(self.memory.latest(), loop_plan, integration, metrics)
        self.memory.replace(updated_memory)

        diary_payload = {
            "loop_counter": loop_counter,
            "theme": loop_plan.theme,
            "goal": loop_plan.goal,
            "block_id": loop_plan.block_id,
            "primary_pillar": loop_plan.primary_pillar,
            "merged_files": integration.files_merged,
            "commit_hash": integration.commit_hash,
            "validation": [item.as_dict() for item in integration.validation],
            "metrics": metrics,
        }
        diary, diary_meta = self.ollama.write_diary(diary_payload)
        self.tui.write_debug_json(debug_dir / "diary.json", {"diary": diary.as_dict(), "provider": diary_meta})

        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "loop",
                "loop_counter": loop_counter,
                "seed_hash": self._seed_hash(),
                "proposal": loop_plan.as_dict(),
                "tasks": [result.as_dict() for result in task_results],
                "integration": integration.as_dict(),
                "validation": [item.as_dict() for item in integration.validation],
                "metrics": metrics,
                "provider": {"planner": planner_meta, "diary": diary_meta},
                "diary": diary.as_dict(),
            }
        )
        self._finalize_loop(runtime, loop_counter, integration.commit_hash, integration.validation, "continue")

    def _record_rest_cycle(self, runtime: dict[str, Any], loop_counter: int, reason: str, provider: dict[str, Any]) -> None:
        memory = self.memory.latest()
        outcomes = dict(memory.get("outcomes") or {})
        outcomes["rest_count"] = outcomes.get("rest_count", 0) + 1
        memory["outcomes"] = outcomes
        self.memory.replace(memory, created_at=now_iso())
        save_current_loop_plan(
            self.config.current_loop_plan_path,
            {
                "loop_counter": loop_counter,
                "theme": "Neutral rest cycle",
                "goal": reason,
                "primary_pillar": ((memory.get("block_planning") or {}).get("current") or {}).get("primary_pillar", "self"),
                "block_id": ((memory.get("block_planning") or {}).get("current") or {}).get("block_id", 0),
                "tasks": [],
                "integration_status": "rest_cycle",
                "validation_status": "skipped",
                "updated_at": now_iso(),
            },
        )
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "rest_cycle",
                "loop_counter": loop_counter,
                "reason": reason,
                "model_provider": provider,
            }
        )
        runtime["loop_count"] = loop_counter + 1
        runtime["last_decision"] = "rest_cycle"
        save_runtime(self.config.runtime_path, runtime)
        export_site(self.root, self.config, self.journal.tail(40), self.memory.latest())
        self._rest(loop_counter)

    def _run_validation(self, changed_files: list[str], loop_counter: int):
        plan = build_validation_plan(self.root, changed_files, loop_counter, self.config.test_mode)
        results = []
        for tier_name, commands in (("fast", plan.fast), ("targeted", plan.targeted), ("full", plan.full)):
            for command in commands:
                completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=False)
                from .models import ValidationResult

                results.append(ValidationResult(completed.returncode == 0, " ".join(command), (completed.stdout + completed.stderr).strip(), tier_name))
        return results

    def _commit_if_valid(self, validation, message: str) -> tuple[str | None, bool]:
        if validation and not all(item.success for item in validation):
            return None, False
        commit_hash = self.opencode.commit(message)
        if not commit_hash:
            return None, False
        pushed, _ = self.opencode.push_current_branch()
        return commit_hash, pushed

    def _finalize_loop(self, runtime: dict[str, Any], loop_counter: int, commit_hash: str | None, validation: list[Any], decision: str) -> None:
        runtime["loop_count"] = loop_counter + 1
        runtime["last_commit"] = commit_hash
        runtime["last_validation"] = "passed" if validation and all(item.success for item in validation) else "failed"
        runtime["last_decision"] = decision
        save_runtime(self.config.runtime_path, runtime)
        export_site(self.root, self.config, self.journal.tail(40), self.memory.latest())
        self._rest(loop_counter)

    def _rest(self, loop_counter: int) -> None:
        seconds = 0 if self.config.test_mode else min(1, self.config.max_rest_seconds)
        self.journal.append(
            {
                "timestamp": now_iso(),
                "entry_type": "rest",
                "loop_counter": loop_counter,
                "decision": "continue",
                "reason": "Continue with another bounded step after a short rest.",
                "sleep_seconds": seconds,
            }
        )
        if seconds:
            time.sleep(seconds)

    def _write_shutdown(self, runtime: dict[str, Any], reason: str) -> None:
        self.journal.append({"timestamp": now_iso(), "entry_type": "shutdown", "loop_counter": runtime.get("loop_count", 0), "reason": reason})
        export_site(self.root, self.config, self.journal.tail(40), self.memory.latest())

    def _seed_hash(self) -> str:
        return hashlib.sha256(self.seed.encode("utf-8")).hexdigest()[:12]

    def _ensure_seed_baseline(self, loop_counter: int) -> None:
        if loop_counter != 0:
            return
        seed_file = self.config.active_game_dir / "design" / "seed_brief.md"
        if seed_file.exists():
            return
        seed_file.parent.mkdir(parents=True, exist_ok=True)
        seed_file.write_text(
            "\n".join(
                [
                    "# Seed Brief",
                    "",
                    f"- Seed prompt: {self.seed}",
                    f"- Seed hash: {self._seed_hash()}",
                    "- Intent: give the active game workspace a concrete starting point before autonomous iteration begins.",
                    "- Initial expectation: turn this seed into a coherent game concept, implementation path, and public journey.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _tracked_changes(self) -> list[str]:
        completed = subprocess.run(["git", "status", "--short"], cwd=self.root, capture_output=True, text=True, check=False)
        changed: list[str] = []
        for line in completed.stdout.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                changed.append(parts[1].strip().rstrip("/"))
        return sorted(set(path for path in changed if not path.startswith("state/") and not path.startswith("site/")))
