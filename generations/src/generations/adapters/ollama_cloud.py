from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from urllib import request

from generations.config import DEFAULT_MODEL, DEFAULT_PROVIDER
from generations.models import DiaryEntry, ExecutionTask, LoopPlan, PlanningRecord
from generations.state import now_iso


class OllamaCloudAdapter:
    def __init__(self) -> None:
        self.provider = os.getenv("GENERATIONS_MODEL_PROVIDER", DEFAULT_PROVIDER)
        self.model = os.getenv("GENERATIONS_MODEL", DEFAULT_MODEL)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.debug = os.getenv("GENERATIONS_DEBUG", "0") == "1"
        self.stubbed = False

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stubbed": self.stubbed,
            "base_url": self.base_url,
            "selected_default_model": DEFAULT_MODEL,
        }

    def plan_checkpoint(self, seed: str, completed_loops: int, memory: dict[str, Any], recent_entries: list[dict[str, Any]]) -> tuple[PlanningRecord, dict[str, Any]]:
        try:
            payload = self._post_generate(self._planning_prompt(seed, completed_loops, memory, recent_entries))
            parsed = json.loads(payload)
            record = PlanningRecord(
                planning_loop=completed_loops,
                generated_at=now_iso(),
                good_end_state=parsed["good_end_state"],
                pillar_assessment=parsed["pillar_assessment"],
                horizon_10=parsed["horizon_10"],
                horizon_100=parsed["horizon_100"],
                horizon_250=parsed["horizon_250"],
                retro=parsed["retro"],
                planner_rationale=parsed["planner_rationale"],
            )
            meta = self.metadata()
            meta["fallback"] = None
            return record, meta
        except Exception as exc:
            self.stubbed = True
            return self._fallback_planning(completed_loops), {**self.metadata(), "fallback": f"{type(exc).__name__}: {exc}"}

    def plan_loop(self, seed: str, loop_counter: int, memory: dict[str, Any]) -> tuple[LoopPlan, dict[str, Any]]:
        try:
            payload = self._post_generate(self._loop_prompt(seed, loop_counter, memory))
            parsed = json.loads(payload)
            tasks = [ExecutionTask(**task) for task in parsed["tasks"][:3]]
            plan = LoopPlan(
                loop_counter=loop_counter,
                theme=parsed["theme"],
                goal=parsed["goal"],
                pillar_budget=parsed["pillar_budget"],
                tasks=tasks,
                integration_policy=parsed["integration_policy"],
                planning_loop=int(parsed["planning_loop"]),
                horizon_10_theme=parsed["horizon_10_theme"],
                rationale=parsed["rationale"],
            )
            meta = self.metadata()
            meta["fallback"] = None
            if self.debug:
                meta["prompt_preview"] = self._loop_prompt(seed, loop_counter, memory)[:2000]
            return plan, meta
        except Exception as exc:
            self.stubbed = True
            plan = self._fallback_loop_plan(seed, loop_counter, memory)
            meta = self.metadata()
            meta["fallback"] = f"{type(exc).__name__}: {exc}"
            if self.debug:
                meta["prompt_preview"] = self._loop_prompt(seed, loop_counter, memory)[:2000]
            return plan, meta

    def write_diary(self, loop_payload: dict[str, Any]) -> tuple[DiaryEntry, dict[str, Any]]:
        try:
            payload = self._post_generate(self._diary_prompt(loop_payload))
            parsed = json.loads(payload)
            diary = DiaryEntry(**parsed)
            meta = self.metadata()
            meta["fallback"] = None
            return diary, meta
        except Exception as exc:
            self.stubbed = True
            diary = DiaryEntry(
                title=f"Loop {loop_payload['loop_counter']} diary",
                mood="focused",
                entry="I made a concrete move inside the current strategic chunk and recorded what still feels incomplete.",
                hopes=["Turn this chunk into a clearer playable loop."],
                worries=["Avoid confusing activity with progress."],
                lessons=["Keep changes coherent and observable."],
                next_desire="Push the current chunk toward a more integrated state.",
            )
            return diary, {**self.metadata(), "fallback": f"{type(exc).__name__}: {exc}"}

    def _post_generate(self, prompt: str) -> str:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0}}).encode("utf-8")
        req = request.Request(f"{self.base_url}/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("response", "")).strip()

    def _planning_prompt(self, seed: str, completed_loops: int, memory: dict[str, Any], recent_entries: list[dict[str, Any]]) -> str:
        return (
            "You are Generations. Produce a planning checkpoint. Return JSON only.\n"
            "Required keys: good_end_state, pillar_assessment, horizon_10, horizon_100, horizon_250, retro, planner_rationale.\n"
            "Each horizon must be a JSON object. pillar_assessment must contain game, self, website, tidiness.\n"
            f"Seed: {seed}\n"
            f"Completed loops: {completed_loops}\n"
            f"Current memory: {json.dumps(memory, sort_keys=True)}\n"
            f"Recent journal entries: {json.dumps(recent_entries[-10:], sort_keys=True)}\n"
        )

    def _loop_prompt(self, seed: str, loop_counter: int, memory: dict[str, Any]) -> str:
        planning = memory.get("planning", {}).get("current")
        return (
            "You are Generations. Plan one loop with up to 3 complementary tasks. Return JSON only.\n"
            "Required keys: theme, goal, pillar_budget, tasks, integration_policy, planning_loop, horizon_10_theme, rationale.\n"
            "Each task requires task_id, scope, objective, allowed_paths, success_signal, priority.\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_counter}\n"
            f"Current planning checkpoint: {json.dumps(planning, sort_keys=True) if planning else 'null'}\n"
            f"Active game: {json.dumps(memory.get('active_game', {}), sort_keys=True)}\n"
            f"Pillar state: {json.dumps(memory.get('pillar_state', {}), sort_keys=True)}\n"
            f"Execution history: {json.dumps(memory.get('execution_history', {}), sort_keys=True)}\n"
            "Keep tasks coherent, complementary, and scoped to platform, active_game, website, or cross_cutting.\n"
        )

    def _diary_prompt(self, loop_payload: dict[str, Any]) -> str:
        return (
            "Write a first-person founder-builder diary entry for this loop. Return JSON only.\n"
            "Required keys: title, mood, entry, hopes, worries, lessons, next_desire.\n"
            f"Loop payload: {json.dumps(loop_payload, sort_keys=True)}\n"
        )

    def _fallback_planning(self, completed_loops: int) -> PlanningRecord:
        return PlanningRecord(
            planning_loop=completed_loops,
            generated_at=now_iso(),
            good_end_state={
                "game": "A coherent, playable logistics game candidate with a credible release path.",
                "self": "A reliable autonomous platform that can plan, execute, review, and validate game work.",
                "website": "A trustworthy public journey page that explains progress and goals clearly.",
                "tidiness": "A coherent repo with strong boundaries, reviewable changes, and dependable validation.",
            },
            pillar_assessment={
                pillar: {"current_state": "Fresh scaffold.", "trajectory": "unclear", "biggest_risk": "Not enough evidence yet.", "confidence": 0.5}
                for pillar in ["game", "self", "website", "tidiness"]
            },
            horizon_10={"theme": "Bootstrap executable motion", "goals": ["Create one platform improvement", "Create one active-game improvement"], "focus_areas": ["platform", "active_game"], "avoid": ["fragmented roots"]},
            horizon_100={"theme": "Reach a playable prototype", "milestones": ["integrated simulation", "basic UI"], "capabilities_needed": ["parallel execution", "tiered validation"]},
            horizon_250={"vision": "A plausible Steam-ready logistics game and a stronger autonomous platform.", "release_shape": "playable release candidate", "platform_shape": "multi-role autonomous studio", "website_shape": "transparent public dashboard"},
            retro={"wins": ["Started clean."], "mistakes": [], "repeated_patterns": [], "surprises": [], "emotional_state": "curious", "open_questions": ["What should the first chunk prove?"]},
            planner_rationale="Start from a clean scaffold and build coherent parallel motion.",
        )

    def _fallback_loop_plan(self, seed: str, loop_counter: int, memory: dict[str, Any]) -> LoopPlan:
        digest = hashlib.sha256(f"{seed}:{loop_counter}".encode("utf-8")).hexdigest()[:8]
        planning = memory.get("planning", {}).get("current") or {}
        tasks = [
            ExecutionTask("A", "active_game", "Advance the active game workspace with one concrete artifact.", ["games/active/src", "games/active/tests", "games/active/design"], "A new active-game artifact exists and is validated.", 1),
            ExecutionTask("B", "platform", "Improve the platform's planning or validation path.", ["generations/src/generations", "generations/tests"], "Platform validation or observability improved.", 2),
            ExecutionTask("C", "website", "Reflect the current loop clearly on the public journey page.", ["generations/src/generations/web"], "Website makes the current loop more legible.", 3),
        ]
        return LoopPlan(
            loop_counter=loop_counter,
            theme=str(planning.get("horizon_10", {}).get("theme", "Coherent multi-task progress")),
            goal=f"Fallback loop plan {digest}: make one game, one platform, and one website step.",
            pillar_budget={"game": 0.4, "self": 0.3, "website": 0.2, "tidiness": 0.1},
            tasks=tasks[: min(3, int(os.getenv('GENERATIONS_PARALLEL_TASKS', '3')))],
            integration_policy={"merge_order": ["A", "B", "C"], "allow_partial_success": True},
            planning_loop=int(planning.get("planning_loop", 0)),
            horizon_10_theme=str(planning.get("horizon_10", {}).get("theme", "Bootstrap executable motion")),
            rationale="Fallback plan keeps all four pillars in view while preserving workspace boundaries.",
        )
