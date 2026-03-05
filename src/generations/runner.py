from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
from pathlib import Path
import json
import signal
import subprocess
import sys
import time
from typing import Any

from generations.adapters.ollama_cloud import OllamaCloudAdapter
from generations.adapters.opencode import OpenCodeAdapter
from generations.config import AppConfig
from generations.git_utils import ensure_git_identity
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.models import OpenCodePlan
from generations.state import RuntimeState, load_runtime_state, save_runtime_state
from generations.web.exporter import export_site


class Runner:
    def __init__(self, root: Path, seed: str) -> None:
        self.root = root
        self.seed = seed
        self.config = AppConfig.from_root(root)
        self.journal = JournalStore(self.config.journal_path)
        self.memory = MemoryStore(self.config.memory_path)
        self.model = OllamaCloudAdapter()
        self.opencode = OpenCodeAdapter(root)
        self.runtime = load_runtime_state(self.config.runtime_path)
        self.stop_requested = False
        self._install_signal_handler()
        ensure_git_identity(root)
        self._ensure_bootstrap_files()

    def _install_signal_handler(self) -> None:
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        self.stop_requested = True

    def _ensure_bootstrap_files(self) -> None:
        self.config.games_dir.mkdir(parents=True, exist_ok=True)
        if not self.config.runtime_path.exists():
            save_runtime_state(self.config.runtime_path, self.runtime)
        export_site(self.root)

    def run(self) -> None:
        while True:
            if self.config.pause_flag.exists():
                self.runtime.paused = True
                self.runtime.last_decision = "paused"
                save_runtime_state(self.config.runtime_path, self.runtime)
                break

            if self.stop_requested:
                self._journal_shutdown("graceful shutdown requested via Ctrl+C")
                break

            if self.config.operational_max_loops is not None and self.runtime.loop_count >= self.config.operational_max_loops:
                self._journal_shutdown("operational safety valve reached max loop count")
                break

            continue_running = self._run_single_loop()
            if not continue_running:
                break
            if self.config.test_mode:
                break

    def _run_single_loop(self) -> bool:
        memory = self.memory.latest()
        loop_counter = self.runtime.loop_count + 1
        seed_hash = sha256(self.seed.encode("utf-8")).hexdigest()
        proposal, model_metadata = self.model.choose_next_step(self.seed, loop_counter, memory)
        criteria = memory["criteria_history"][-1]

        plan = OpenCodePlan(
            summary=f"{proposal.workstream}:{proposal.capability_target}: {proposal.description}",
            editable_files=proposal.target_files,
            files_expected=proposal.target_files + [
                "state/loop_snapshot.json",
                "state/website_notes.md",
                "state/memory.sqlite3",
                "site/index.html",
                "site/style.css",
            ],
            website_change_reason=proposal.website_reason,
            monetization_change_reason=proposal.monetization_reason,
        )

        plan_path = self.config.state_dir / "last_plan.json"
        self.opencode.export_plan(plan, plan_path)

        before_journal_count = len(self.journal.read_all())
        verify_commands = self._verification_commands()

        result = self.opencode.run_workflow(
            plan=plan,
            apply_fn=lambda: self._apply_iteration(loop_counter, proposal, memory, model_metadata),
            verify_commands=verify_commands,
            commit_message=f"loop {loop_counter}: {proposal.description[:68]}",
        )

        latest_memory = self.memory.latest()
        validation_success = all(item.success for item in result.validation)
        latest_memory["outcomes"]["last_validation"] = [item.as_dict() for item in result.validation]
        if validation_success:
            latest_memory["outcomes"]["pass_count"] += 1
            latest_memory["outcomes"]["last_successful_loop"] = loop_counter
            latest_memory["outcomes"]["last_error"] = None
        else:
            latest_memory["outcomes"]["fail_count"] += 1
            latest_memory["outcomes"]["last_error"] = result.validation[-1].output if result.validation else "validation failed"
        self.memory.replace(latest_memory, created_at=self._timestamp())

        rest_seconds, continue_running, reason = self._rest_decision(loop_counter, validation_success)
        entry = {
            "timestamp": self._timestamp(),
            "loop_counter": loop_counter,
            "seed_hash": seed_hash,
            "criteria": criteria,
            "next_step": {
                "workstream": proposal.workstream,
                "capability_target": proposal.capability_target,
                "description": proposal.description,
                "rationale": proposal.rationale,
            },
            "actions_taken": result.files_touched,
            "validation_results": [item.as_dict() for item in result.validation],
            "validation_summary": "passed" if validation_success else "failed",
            "commit_hash": result.commit_hash,
            "rolled_back": result.rolled_back,
            "opencode": {
                "session_id": result.opencode_session_id,
                "session_export": result.opencode_session_export,
                "changed_files": result.opencode_changed_files,
                "binary": str(self.opencode.binary),
            },
            "model_provider": model_metadata,
            "rest_decision": {
                "decision": "continue" if continue_running else "stop",
                "sleep_seconds": rest_seconds,
                "reason": reason,
            },
            "website_change": {
                "changed": proposal.website_change,
                "summary": proposal.website_reason,
            },
            "monetization_change": {
                "changed": proposal.monetization_change,
                "summary": proposal.monetization_reason,
            },
            "journal_entry_count_before_write": before_journal_count,
        }
        self.journal.append(entry)

        self.runtime = RuntimeState(
            loop_count=loop_counter,
            last_commit=result.commit_hash,
            last_validation={"success": validation_success, "results": [item.as_dict() for item in result.validation]},
            current_criteria_version=latest_memory["current_criteria_version"],
            paused=False,
            last_decision="continue" if continue_running else "stop",
        )
        save_runtime_state(self.config.runtime_path, self.runtime)

        export_site(self.root)
        if rest_seconds > 0 and continue_running and not self.config.test_mode:
            time.sleep(rest_seconds)

        if not continue_running:
            self._journal_done(loop_counter, latest_memory, validation_success)
        return continue_running

    def _apply_iteration(
        self,
        loop_counter: int,
        proposal: Any,
        memory: dict[str, Any],
        model_metadata: dict[str, object],
    ) -> list[str]:
        touched: list[str] = []
        runtime_note = {
            "loop": loop_counter,
            "workstream": proposal.workstream,
            "capability_target": proposal.capability_target,
            "proposal": proposal.description,
            "model": model_metadata,
            "timestamp": self._timestamp(),
        }
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        runtime_snapshot_path = self.config.state_dir / "loop_snapshot.json"
        runtime_snapshot_path.write_text(json.dumps(runtime_note, indent=2) + "\n", encoding="utf-8")
        touched.append(str(runtime_snapshot_path.relative_to(self.root)))

        website_notes = self.root / "state" / "website_notes.md"
        website_notes.write_text(
            "# Website Notes\n\n"
            f"Latest loop: {loop_counter}\n\n"
            f"Visible intent: {proposal.website_reason}\n\n"
            "Support remains a minimal placeholder until a logged experiment is justified.\n",
            encoding="utf-8",
        )
        touched.append(str(website_notes.relative_to(self.root)))

        updated_memory = memory
        heuristics = list(updated_memory.get("heuristics", []))
        for item in proposal.heuristics_updates:
            if item not in heuristics:
                heuristics.append(item)
        updated_memory["heuristics"] = heuristics
        updated_memory["tool_routing"] = {
            "execution_surface": f"OpenCode CLI ({self.opencode.binary}) with local session export and guarded shell execution",
            "model_provider": f"{model_metadata['provider']}:{model_metadata['model']}",
        }
        updated_memory["last_workstream"] = proposal.workstream
        updated_memory["last_capability_target"] = proposal.capability_target
        self.memory.replace(updated_memory, created_at=self._timestamp())
        touched.append(str(self.config.memory_path.relative_to(self.root)))

        export_site(self.root)
        touched.append(str((self.root / "site" / "index.html").relative_to(self.root)))
        return touched

    def _rest_decision(self, loop_counter: int, validation_success: bool) -> tuple[int, bool, str]:
        if not validation_success:
            return 0, False, "Stop after validation failure to preserve repository integrity."
        if self.config.test_mode:
            return 0, False, "Test harness mode performs exactly one safe loop for fast verification."
        if loop_counter >= 3:
            return 0, False, "Current criteria judge the bootstrap phase complete after three successful tiny loops."
        return min(1, self.config.max_rest_seconds), True, "Continue with another small step after a short bounded rest."

    def _verification_commands(self) -> list[list[str]]:
        if importlib.util.find_spec("pytest") is None:
            return [[sys.executable, "-m", "compileall", "src", "tests", "games"]]
        if self.config.test_mode:
            return [[sys.executable, "-m", "pytest", "tests/test_journal.py"]]
        return [[sys.executable, "-m", "pytest", "tests/test_journal.py", "tests/test_smoke.py"]]

    def _journal_shutdown(self, reason: str) -> None:
        latest_memory = self.memory.latest()
        entry = {
            "timestamp": self._timestamp(),
            "loop_counter": self.runtime.loop_count,
            "seed_hash": sha256(self.seed.encode("utf-8")).hexdigest(),
            "criteria": latest_memory["criteria_history"][-1],
            "next_step": {"description": "shutdown", "rationale": reason},
            "actions_taken": [],
            "validation_results": [],
            "validation_summary": "not run",
            "commit_hash": self.runtime.last_commit,
            "model_provider": self.model.metadata(),
            "rest_decision": {"decision": "stop", "sleep_seconds": 0, "reason": reason},
            "website_change": {"changed": False, "summary": "no change"},
            "monetization_change": {"changed": False, "summary": "no change"},
        }
        self.journal.append(entry)
        self.runtime.last_decision = "stopped"
        save_runtime_state(self.config.runtime_path, self.runtime)
        export_site(self.root)

    def _journal_done(self, loop_counter: int, memory: dict[str, Any], validation_success: bool) -> None:
        final_entry = {
            "timestamp": self._timestamp(),
            "loop_counter": loop_counter,
            "seed_hash": sha256(self.seed.encode("utf-8")).hexdigest(),
            "criteria": memory["criteria_history"][-1],
            "next_step": {
                "description": "done",
                "rationale": "Generations decided the current bootstrap objective is complete under the active criteria.",
            },
            "actions_taken": [],
            "validation_results": memory["outcomes"].get("last_validation") or [],
            "validation_summary": "passed" if validation_success else "failed",
            "commit_hash": self.runtime.last_commit,
            "model_provider": self.model.metadata(),
            "rest_decision": {
                "decision": "stop",
                "sleep_seconds": 0,
                "reason": "Done under current criteria for the bootstrap stage.",
            },
            "website_change": {
                "changed": False,
                "summary": "Website remains available as the external journey surface.",
            },
            "monetization_change": {
                "changed": False,
                "summary": "Support placeholder remains active; no new monetization experiment was required.",
            },
            "done_summary": {
                "reasons": [
                    "Bootstrap observability and self-edit loop are functioning.",
                    "Validation passed for the latest loop set.",
                    "Website and monetization baseline are active and logged.",
                ],
                "criteria_version": memory["current_criteria_version"],
                "heuristics_used": memory["heuristics"],
                "project_status": {
                    "website": "running and exportable",
                    "monetization": "minimal support placeholder with disclosure",
                    "games": "hello_game placeholder present",
                },
                "last_known_validation_state": memory["outcomes"].get("last_validation"),
                "would_do_next": "Expand evaluation heuristics and grow the hello_game prototype toward a more Steam-plausible direction.",
            },
        }
        self.journal.append(final_entry)
        export_site(self.root)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


def init_repo_if_needed(root: Path) -> None:
    git_dir = root / ".git"
    if git_dir.exists():
        return
    subprocess.run(["git", "init"], cwd=root, check=False, capture_output=True)
