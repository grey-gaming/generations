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
from generations.memory.store import DEFAULT_MEMORY, MemoryStore
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
        self._log_run_header()
        while True:
            if self.config.pause_flag.exists():
                self.runtime.paused = True
                self.runtime.last_decision = "paused"
                save_runtime_state(self.config.runtime_path, self.runtime)
                self._log("paused", "pause flag detected")
                break

            if self.stop_requested:
                self._journal_shutdown("graceful shutdown requested via Ctrl+C")
                self._log("stop", "graceful shutdown requested via Ctrl+C")
                break

            if self.config.operational_max_loops is not None and self.runtime.loop_count >= self.config.operational_max_loops:
                self._journal_shutdown("operational safety valve reached max loop count")
                self._log("stop", "operational max loop limit reached")
                break

            continue_running = self._run_single_loop()
            if not continue_running:
                break
            if self.config.test_mode:
                break

    def _run_single_loop(self) -> bool:
        memory = self._normalize_memory(self.memory.latest())
        self.memory.replace(memory, created_at=self._timestamp())
        loop_counter = self.runtime.loop_count + 1
        seed_hash = sha256(self.seed.encode("utf-8")).hexdigest()
        proposal, model_metadata = self.model.choose_next_step(self.seed, loop_counter, memory)
        criteria = memory["criteria_history"][-1]
        if self.config.debug and model_metadata.get("prompt_preview"):
            print("debug model_prompt_preview:", flush=True)
            print(str(model_metadata["prompt_preview"]), flush=True)

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
        metrics = self._score_loop(proposal, result, validation_success)
        latest_memory["outcomes"]["last_validation"] = [item.as_dict() for item in result.validation]
        if validation_success:
            latest_memory["outcomes"]["pass_count"] += 1
            latest_memory["outcomes"]["last_successful_loop"] = loop_counter
            latest_memory["outcomes"]["last_error"] = None
        else:
            latest_memory["outcomes"]["fail_count"] += 1
            latest_memory["outcomes"]["last_error"] = result.validation[-1].output if result.validation else "validation failed"
            heuristics = list(latest_memory.get("heuristics", []))
            failure_heuristic = "Avoid no-op loops: each successful iteration should produce a meaningful repo edit outside generated state."
            if failure_heuristic not in heuristics:
                heuristics.append(failure_heuristic)
            latest_memory["heuristics"] = heuristics
        latest_memory["evaluation_metrics"] = self._update_metrics_memory(
            latest_memory.get("evaluation_metrics", {}),
            loop_counter,
            proposal,
            metrics,
        )
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
            "evaluation_metrics": metrics,
            "commit_hash": result.commit_hash,
            "rolled_back": result.rolled_back,
            "opencode": {
                "session_id": result.opencode_session_id,
                "session_export": result.opencode_session_export,
                "changed_files": result.opencode_changed_files,
                "pushed": result.pushed,
                "push_output": result.push_output,
                "debug_stdout_path": result.debug_stdout_path,
                "debug_stderr_path": result.debug_stderr_path,
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
        self._log_loop_result(loop_counter, proposal, result, validation_success, continue_running, reason)

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

        if not continue_running and validation_success:
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
        strategic_intent = dict(updated_memory.get("strategic_intent", {}))
        questions = list(strategic_intent.get("next_big_questions", []))
        if proposal.workstream == "game_workspace":
            strategic_intent["current_game_thesis"] = (
                "Investigate a transport/logistics game with economy, routing, progression, and world simulation."
            )
        if proposal.capability_target not in {"journaling", "website", "memory"}:
            question = f"What larger arc does {proposal.capability_target} unlock for the eventual game or platform?"
            if question not in questions:
                questions.append(question)
        strategic_intent["next_big_questions"] = questions[-6:]
        updated_memory["strategic_intent"] = strategic_intent
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
                    "games": "space_logistics seed workspace present",
                },
                "last_known_validation_state": memory["outcomes"].get("last_validation"),
                "would_do_next": "Grow the space_logistics workspace from design toward a more credible playable prototype.",
            },
        }
        self.journal.append(final_entry)
        export_site(self.root)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_run_header(self) -> None:
        print(
            f"run start: seed_sha={sha256(self.seed.encode('utf-8')).hexdigest()[:12]} "
            f"loop_start={self.runtime.loop_count} criteria_v={self.runtime.current_criteria_version} "
            f"debug={'on' if self.config.debug else 'off'} agent={self.config.opencode_agent}",
            flush=True,
        )

    def _log_loop_result(
        self,
        loop_counter: int,
        proposal: Any,
        result: Any,
        validation_success: bool,
        continue_running: bool,
        reason: str,
    ) -> None:
        changed_files = ",".join(result.opencode_changed_files[:4]) if result.opencode_changed_files else "-"
        commit_hash = result.commit_hash[:10] if result.commit_hash else "none"
        print(
            f"loop={loop_counter} workstream={proposal.workstream} capability={proposal.capability_target} "
            f"validation={'pass' if validation_success else 'fail'} commit={commit_hash} "
            f"opencode_files={changed_files} decision={'continue' if continue_running else 'stop'}",
            flush=True,
        )
        latest_metrics = self.memory.latest().get("evaluation_metrics", {}).get("current", {})
        if latest_metrics:
            print(
                "metrics: "
                f"creativity={latest_metrics.get('creativity', 0):.2f} "
                f"code_change={latest_metrics.get('code_change', 0):.2f} "
                f"review={latest_metrics.get('review_quality', 0):.2f} "
                f"game={latest_metrics.get('game_progress', 0):.2f} "
                f"obs={latest_metrics.get('observability', 0):.2f} "
                f"balance={latest_metrics.get('balance', 0):.2f}",
                flush=True,
            )
        print(f"reason: {reason}", flush=True)
        if self.config.debug:
            latest_model = self.memory.latest().get("outcomes", {}).get("last_error")
            print(
                f"debug opencode_stdout={result.debug_stdout_path or '-'} "
                f"opencode_stderr={result.debug_stderr_path or '-'}",
                flush=True,
            )
            if latest_model:
                print(f"debug last_error={latest_model}", flush=True)

    def _log(self, event: str, message: str) -> None:
        print(f"{event}: {message}", flush=True)

    def _normalize_memory(self, memory: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(memory)
        heuristics = list(normalized.get("heuristics", []))
        old = "Favor tiny, coherent edits over ambitious rewrites."
        new = "Favor coherent, reviewable steps inside a larger strategic arc."
        if old in heuristics:
            heuristics = [new if item == old else item for item in heuristics]
        if new not in heuristics:
            heuristics.insert(0, new)
        normalized["heuristics"] = heuristics

        if "strategic_intent" not in normalized:
            normalized["strategic_intent"] = DEFAULT_MEMORY["strategic_intent"]
        if "evaluation_metrics" not in normalized:
            normalized["evaluation_metrics"] = DEFAULT_MEMORY["evaluation_metrics"]
        return normalized

    def _score_loop(self, proposal: Any, result: Any, validation_success: bool) -> dict[str, float]:
        changed_files = [
            path for path in result.files_touched
            if not path.startswith("state/") and not path.startswith("site/")
        ]
        opencode_changed = [
            path for path in result.opencode_changed_files
            if not path.startswith("state/") and not path.startswith("site/")
        ]
        all_meaningful = sorted(set(changed_files + opencode_changed))
        creativity = 0.25
        if proposal.capability_target in {"game_design", "game_pipeline", "game_prototype", "tooling", "evaluation"}:
            creativity += 0.25
        if proposal.workstream == "game_workspace":
            creativity += 0.2
        if len(all_meaningful) >= 2:
            creativity += 0.2
        if proposal.website_change and proposal.capability_target == "website":
            creativity += 0.1

        code_change = min(1.0, 0.35 * len(all_meaningful))
        if any(path.startswith("src/") for path in all_meaningful):
            code_change += 0.25
        if any(path.startswith("games/") for path in all_meaningful):
            code_change += 0.25
        code_change = min(1.0, code_change)

        review_quality = 0.2 if validation_success else 0.0
        if result.validation:
            review_quality += 0.5 if validation_success else 0.1
        if any("pytest" in item.command for item in result.validation):
            review_quality += 0.2
        if result.rolled_back:
            review_quality += 0.1
        review_quality = min(1.0, review_quality)

        game_progress = 0.1
        if proposal.workstream == "game_workspace":
            game_progress += 0.35
        if proposal.capability_target in {"game_design", "game_pipeline", "game_prototype"}:
            game_progress += 0.3
        if any(path.startswith("games/") for path in all_meaningful):
            game_progress += 0.25
        game_progress = min(1.0, game_progress)

        observability = 0.2
        if proposal.capability_target in {"journaling", "memory", "website", "evaluation"}:
            observability += 0.25
        if proposal.website_change:
            observability += 0.15
        if self.config.journal_path.exists() and self.config.runtime_path.exists():
            observability += 0.2
        observability = min(1.0, observability)

        values = [creativity, code_change, review_quality, game_progress, observability]
        balance = max(0.0, 1.0 - (max(values) - min(values)))
        return {
            "creativity": round(creativity, 2),
            "code_change": round(code_change, 2),
            "review_quality": round(review_quality, 2),
            "game_progress": round(game_progress, 2),
            "observability": round(observability, 2),
            "balance": round(balance, 2),
        }

    def _update_metrics_memory(
        self,
        metrics_block: dict[str, Any],
        loop_counter: int,
        proposal: Any,
        metrics: dict[str, float],
    ) -> dict[str, Any]:
        history = list(metrics_block.get("recent_history", []))
        history.append(
            {
                "loop": loop_counter,
                "workstream": proposal.workstream,
                "capability_target": proposal.capability_target,
                "metrics": metrics,
            }
        )
        history = history[-10:]
        rolling_average: dict[str, float] = {}
        keys = ["creativity", "code_change", "review_quality", "game_progress", "observability", "balance"]
        for key in keys:
            values = [float(item["metrics"].get(key, 0.0)) for item in history]
            rolling_average[key] = round(sum(values) / len(values), 2) if values else 0.0
        return {
            "current": metrics,
            "rolling_average": rolling_average,
            "recent_history": history,
            "notes": metrics_block.get("notes", [
                "Metrics guide balancing, but the model still chooses the next step.",
                "Low code_change or game_progress should bias future loops toward meaningful repo edits.",
            ]),
        }


def init_repo_if_needed(root: Path) -> None:
    git_dir = root / ".git"
    if git_dir.exists():
        return
    subprocess.run(["git", "init"], cwd=root, check=False, capture_output=True)
