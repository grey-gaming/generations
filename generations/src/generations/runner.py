from __future__ import annotations

import hashlib
import signal
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
from .state import default_runtime, now_iso, save_current_loop_plan, save_runtime, load_runtime
from .tui import TUI
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
        memory = self.memory.latest()
        planning_record = self.planner.ensure_checkpoint(self.seed, loop_counter)
        loop_plan, planner_meta = self.ollama.plan_loop(self.seed, loop_counter, memory)
        debug_dir = self.config.runs_dir / f"loop-{loop_counter:04d}"
        debug_dir.mkdir(parents=True, exist_ok=True)
        self.tui.write_debug_json(debug_dir / "planner.json", {"loop_plan": loop_plan.as_dict(), "provider": planner_meta})

        current_loop_plan = {
            "loop_counter": loop_counter,
            "theme": loop_plan.theme,
            "goal": loop_plan.goal,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "scope": task.scope,
                    "objective": task.objective,
                    "status": "planned",
                    "success_signal": task.success_signal,
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
            "planning_loop": planning_record.planning_loop,
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
                "plan_ref": {
                    "planning_loop": planning_record.planning_loop,
                    "horizon_10_theme": planning_record.horizon_10.get("theme", ""),
                },
                "proposal": loop_plan.as_dict(),
                "tasks": [result.as_dict() for result in task_results],
                "integration": integration.as_dict(),
                "validation": [item.as_dict() for item in integration.validation],
                "metrics": metrics,
                "provider": {"planner": planner_meta, "diary": diary_meta},
                "diary": diary.as_dict(),
            }
        )

        runtime["loop_count"] = loop_counter + 1
        runtime["last_commit"] = integration.commit_hash
        runtime["last_validation"] = "passed" if validation_passed else "failed"
        runtime["last_decision"] = "continue"
        save_runtime(self.config.runtime_path, runtime)

        self.memory.update_current_loop_plan(None)
        export_site(self.root, self.config, self.journal.tail(20), self.memory.latest())
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
        export_site(self.root, self.config, self.journal.tail(20), self.memory.latest())

    def _seed_hash(self) -> str:
        return hashlib.sha256(self.seed.encode("utf-8")).hexdigest()[:12]
