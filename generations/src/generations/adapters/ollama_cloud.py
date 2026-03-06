from __future__ import annotations

import json
import os
from typing import Any
from urllib import request

from generations.config import DEFAULT_MODEL, DEFAULT_PROVIDER
from generations.models import BlockPlan, DiaryEntry, ExecutionTask, LongTermVisionRecord, LoopPlan, RetrospectiveRecord
from generations.state import now_iso


class OllamaCloudAdapter:
    def __init__(self) -> None:
        self.provider = os.getenv("GENERATIONS_MODEL_PROVIDER", DEFAULT_PROVIDER)
        self.model = os.getenv("GENERATIONS_MODEL", DEFAULT_MODEL)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.debug = os.getenv("GENERATIONS_DEBUG", "0") == "1"
        self.test_mode = os.getenv("GENERATIONS_TEST_MODE", "0") == "1"
        self.stubbed = False

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stubbed": self.stubbed,
            "base_url": self.base_url,
            "selected_default_model": DEFAULT_MODEL,
        }

    def plan_long_term_vision(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        recent_entries: list[dict[str, Any]],
        *,
        current_version: int,
    ) -> tuple[LongTermVisionRecord | None, dict[str, Any]]:
        if self.test_mode:
            record = self._test_vision(seed, loop_counter, current_version)
            return record, {**self.metadata(), "fallback": None, "test_mode": True}
        prompt = self._vision_prompt(seed, loop_counter, memory, recent_entries, current_version)
        try:
            payload = self._post_generate(prompt)
            parsed = json.loads(payload)
            record = LongTermVisionRecord(
                version=current_version + 1,
                generated_at=now_iso(),
                refined_at_loop=loop_counter,
                index_summary=str(parsed["index_summary"]),
                pillars={name: self._normalize_vision_pillar(name, content) for name, content in parsed["pillars"].items()},
                change_summary=str(parsed.get("change_summary") or "Initial long-term vision created."),
            )
            return record, self._meta(prompt)
        except Exception as exc:
            return None, self._failure_meta(exc, prompt)

    def plan_initial_self_block(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        vision: dict[str, Any],
    ) -> tuple[BlockPlan | None, dict[str, Any]]:
        if self.test_mode:
            return self._test_initial_self_block(loop_counter), {**self.metadata(), "fallback": None, "test_mode": True}
        prompt = self._initial_block_prompt(seed, loop_counter, memory, vision)
        try:
            payload = self._post_generate(prompt)
            parsed = json.loads(payload)
            return self._block_from_json(parsed, block_id=1, planning_loop=loop_counter), self._meta(prompt)
        except Exception as exc:
            return None, self._failure_meta(exc, prompt)

    def plan_block(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        vision: dict[str, Any],
        latest_retro: dict[str, Any] | None,
        *,
        block_id: int,
    ) -> tuple[BlockPlan | None, dict[str, Any]]:
        if self.test_mode:
            return self._test_block(loop_counter, block_id), {**self.metadata(), "fallback": None, "test_mode": True}
        prompt = self._block_prompt(seed, loop_counter, memory, vision, latest_retro, block_id)
        try:
            payload = self._post_generate(prompt)
            parsed = json.loads(payload)
            return self._block_from_json(parsed, block_id=block_id, planning_loop=loop_counter), self._meta(prompt)
        except Exception as exc:
            return None, self._failure_meta(exc, prompt)

    def write_retrospective(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        prior_block: dict[str, Any],
        block_entries: list[dict[str, Any]],
    ) -> tuple[RetrospectiveRecord | None, dict[str, Any]]:
        if self.test_mode:
            return self._test_retrospective(loop_counter, prior_block), {**self.metadata(), "fallback": None, "test_mode": True}
        prompt = self._retrospective_prompt(seed, loop_counter, memory, prior_block, block_entries)
        try:
            payload = self._post_generate(prompt)
            parsed = json.loads(payload)
            record = RetrospectiveRecord(
                block_id=int(prior_block["block_id"]),
                retrospective_loop=loop_counter,
                primary_pillar=str(prior_block["primary_pillar"]),
                execution_range=tuple(prior_block["execution_range"]),
                intended_outcomes=list(parsed.get("intended_outcomes") or prior_block.get("target_outcomes") or []),
                actual_outcomes=_string_list(parsed.get("actual_outcomes")),
                wins=_string_list(parsed.get("wins")),
                failures=_string_list(parsed.get("failures")),
                stalls=_string_list(parsed.get("stalls")),
                surprises=_string_list(parsed.get("surprises")),
                metric_reflection={
                    "helpful": _string_list((parsed.get("metric_reflection") or {}).get("helpful")),
                    "misleading": _string_list((parsed.get("metric_reflection") or {}).get("misleading")),
                },
                carry_forward=_string_list(parsed.get("carry_forward")),
                change_next_time=_string_list(parsed.get("change_next_time")),
                summary=str(parsed.get("summary") or "Retrospective recorded."),
            )
            return record, self._meta(prompt)
        except Exception as exc:
            return None, self._failure_meta(exc, prompt)

    def plan_execution_loop(
        self,
        seed: str,
        loop_counter: int,
        memory: dict[str, Any],
        block_plan: dict[str, Any],
        vision: dict[str, Any] | None,
    ) -> tuple[LoopPlan | None, dict[str, Any]]:
        if self.test_mode:
            return self._test_loop(loop_counter, block_plan), {**self.metadata(), "fallback": None, "test_mode": True}
        prompt = self._execution_prompt(seed, loop_counter, memory, block_plan, vision)
        try:
            payload = self._post_generate(prompt)
            parsed = json.loads(payload)
            if parsed.get("status") == "rest_required":
                meta = self._meta(prompt)
                meta["rest_required"] = parsed.get("reason") or "Planner requested neutral rest."
                return None, meta
            tasks = [ExecutionTask(**self._normalize_task(task)) for task in (parsed.get("tasks") or [])[:3]]
            return LoopPlan(
                loop_counter=loop_counter,
                theme=str(parsed["theme"]),
                goal=str(parsed["goal"]),
                primary_pillar=str(parsed.get("primary_pillar") or block_plan["primary_pillar"]),
                block_id=int(parsed.get("block_id") or block_plan["block_id"]),
                planning_mode=False,
                block_plan_ref=int(block_plan["block_id"]),
                support_task_policy={"requires_justification": True},
                pillar_budget=_pillar_budget(parsed.get("pillar_budget"), str(block_plan["primary_pillar"])),
                tasks=tasks,
                integration_policy=parsed.get("integration_policy") or {"merge_order": [task.task_id for task in tasks], "allow_partial_success": True},
                rationale=str(parsed.get("rationale") or "Execution loop aligns to the active block."),
            ), self._meta(prompt)
        except Exception as exc:
            return None, self._failure_meta(exc, prompt)

    def write_diary(self, loop_payload: dict[str, Any]) -> tuple[DiaryEntry, dict[str, Any]]:
        if self.test_mode:
            diary = DiaryEntry(
                title=f"Loop {loop_payload['loop_counter']} diary",
                mood="focused",
                entry="I stayed inside the active block, recorded what landed, and kept the next move legible.",
                hopes=["Turn the current block into durable capability."],
                worries=["Avoid cosmetic motion that does not advance the block."],
                lessons=["Block discipline matters more than local novelty."],
                next_desire="Use the next loop to deepen the current block rather than scatter effort.",
            )
            return diary, {**self.metadata(), "fallback": None, "test_mode": True}
        prompt = self._diary_prompt(loop_payload)
        try:
            payload = self._post_generate(prompt)
            parsed = json.loads(payload)
            diary = DiaryEntry(**parsed)
            return diary, self._meta(prompt)
        except Exception as exc:
            self.stubbed = True
            diary = DiaryEntry(
                title=f"Loop {loop_payload['loop_counter']} diary",
                mood="focused",
                entry="I kept the current block moving and recorded the most important constraint I can see from here.",
                hopes=["Make the block more coherent next loop."],
                worries=["Avoid telling a better story than the code deserves."],
                lessons=["Keep the block objective visible."],
                next_desire="Land a cleaner change on the next loop.",
            )
            return diary, self._failure_meta(exc, prompt)

    def _post_generate(self, prompt: str) -> str:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0}}).encode("utf-8")
        req = request.Request(f"{self.base_url}/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("response", "")).strip()

    def _meta(self, prompt: str) -> dict[str, Any]:
        meta = self.metadata()
        meta["fallback"] = None
        if self.debug:
            meta["prompt_preview"] = prompt[:4000]
        return meta

    def _failure_meta(self, exc: Exception, prompt: str) -> dict[str, Any]:
        self.stubbed = True
        meta = self.metadata()
        meta["fallback"] = f"{type(exc).__name__}: {exc}"
        if self.debug:
            meta["prompt_preview"] = prompt[:4000]
        return meta

    def _vision_prompt(self, seed: str, loop_counter: int, memory: dict[str, Any], recent_entries: list[dict[str, Any]], current_version: int) -> str:
        return (
            "You are Generations, an autonomous studio that is trying to become capable of building a distinctive commercial game.\n"
            "This is a long-horizon vision exercise, not a loop task list. Define the long-term purpose of exactly three pillars: self, game, monetization_platform. Return JSON only.\n"
            "Required keys: index_summary, change_summary, pillars.\n"
            "pillars must contain self, game, monetization_platform. Each pillar must include: purpose, good_end_state, failure_modes, relationships, summary, content.\n"
            "The content for each pillar must be at least 500 words and should read like a serious internal manifesto, not a placeholder.\n"
            "For self: describe the autonomous platform, planning discipline, validation, observability, website, and operator trust.\n"
            "For game: describe the kind of transport/logistics game worth building, what makes it distinctive, and what shippable quality means.\n"
            "For monetization_platform: describe the honest commercial surface, audience relationship, support model, and what good restraint looks like before product proof.\n"
            "Be concrete about failure modes and tensions between pillars.\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_counter}\n"
            f"Current vision version: {current_version}\n"
            f"Current memory: {json.dumps(memory, sort_keys=True)}\n"
            f"Recent entries: {json.dumps(recent_entries[-10:], sort_keys=True)}\n"
        )

    def _initial_block_prompt(self, seed: str, loop_counter: int, memory: dict[str, Any], vision: dict[str, Any]) -> str:
        return (
            "You are Generations. Create the first 9-loop execution block after the long-term vision. Return JSON only.\n"
            "Required keys: primary_pillar, why_this_pillar_now, target_outcomes, sub_goals, allowed_support_work, explicit_non_goals, success_signals, failure_signals, expected_artifacts, metrics_to_watch, risks, review_focus.\n"
            "The block must be focused on self. This means improving the autonomous platform, planning, validation, observability, and the public journey page.\n"
            "Do not drift into general game building yet. The point is to make the system itself sharper for the next blocks.\n"
            "Target outcomes should describe specific capability gains, not slogans.\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_counter}\n"
            f"Long-term vision: {json.dumps(vision, sort_keys=True)}\n"
            f"Memory: {json.dumps(memory, sort_keys=True)}\n"
        )

    def _block_prompt(self, seed: str, loop_counter: int, memory: dict[str, Any], vision: dict[str, Any], latest_retro: dict[str, Any] | None, block_id: int) -> str:
        return (
            "You are Generations. Choose the next 9-loop block. Return JSON only.\n"
            "Required keys: primary_pillar, why_this_pillar_now, target_outcomes, sub_goals, allowed_support_work, explicit_non_goals, success_signals, failure_signals, expected_artifacts, metrics_to_watch, risks, review_focus.\n"
            "primary_pillar must be one of self, game, monetization_platform.\n"
            "Use the latest retrospective and the long-term vision to choose the single most leveraged pillar for the next 9 execution loops.\n"
            "Write a plan that would let an execution agent know what artifacts should plausibly exist by the end of the block.\n"
            "Expected_artifacts should name real outputs such as tests, modules, design documents, vision updates, or website sections.\n"
            "Explicit_non_goals should make it obvious what the block is refusing to chase.\n"
            f"Seed: {seed}\n"
            f"Planning loop: {loop_counter}\n"
            f"Next block id: {block_id}\n"
            f"Long-term vision: {json.dumps(vision, sort_keys=True)}\n"
            f"Latest retrospective: {json.dumps(latest_retro, sort_keys=True) if latest_retro else 'null'}\n"
            f"Memory: {json.dumps(memory, sort_keys=True)}\n"
        )

    def _retrospective_prompt(self, seed: str, loop_counter: int, memory: dict[str, Any], prior_block: dict[str, Any], block_entries: list[dict[str, Any]]) -> str:
        return (
            "You are Generations. Write a structured retrospective for the completed 10-loop block. Return JSON only.\n"
            "Required keys: intended_outcomes, actual_outcomes, wins, failures, stalls, surprises, metric_reflection, carry_forward, change_next_time, summary.\n"
            "Be honest. Distinguish between work that actually landed and work that was merely described. Call out repeated no-op behavior, weak tasks, or misleading metrics when present.\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_counter}\n"
            f"Prior block: {json.dumps(prior_block, sort_keys=True)}\n"
            f"Block entries: {json.dumps(block_entries[-20:], sort_keys=True)}\n"
            f"Memory: {json.dumps(memory, sort_keys=True)}\n"
        )

    def _execution_prompt(self, seed: str, loop_counter: int, memory: dict[str, Any], block_plan: dict[str, Any], vision: dict[str, Any] | None) -> str:
        return (
            "You are Generations. Plan one execution loop inside the active 10-loop block. Return JSON only.\n"
            "Required keys: status, theme, goal, primary_pillar, block_id, pillar_budget, tasks, integration_policy, rationale.\n"
            "status must be ok or rest_required. If rest_required, include reason and an empty tasks list.\n"
            "Each task must include task_id, scope, objective, allowed_paths, success_signal, priority, support_reason.\n"
            "At least 2 tasks must directly support the block's primary pillar when multiple tasks are returned.\n"
            "Choose tasks that create or modify real artifacts. Prefer code, tests, design docs, or website sections that materially advance the block.\n"
            "Do not return placeholder tasks that mostly narrate intent. If the right move is to rest because no valid task is available, say rest_required.\n"
            "When the primary pillar is self, tasks should improve the autonomous platform, validation, observability, or website clarity.\n"
            "When the primary pillar is game, tasks should move the active game toward executable systems, tests, or solid design artifacts.\n"
            "When the primary pillar is monetization_platform, tasks should improve honest commercial/support surfaces and the supporting governance around them.\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_counter}\n"
            f"Current block plan: {json.dumps(block_plan, sort_keys=True)}\n"
            f"Long-term vision: {json.dumps(vision, sort_keys=True) if vision else 'null'}\n"
            f"Metrics: {json.dumps((memory.get('evaluation_metrics') or {}).get('rolling_average', {}), sort_keys=True)}\n"
            f"Execution history: {json.dumps(memory.get('execution_history', {}), sort_keys=True)}\n"
            "Metrics are signals, not commands. Stay inside the current block.\n"
        )

    def _diary_prompt(self, loop_payload: dict[str, Any]) -> str:
        return (
            "Write a first-person founder-builder diary entry for this loop. Return JSON only.\n"
            "Required keys: title, mood, entry, hopes, worries, lessons, next_desire.\n"
            f"Loop payload: {json.dumps(loop_payload, sort_keys=True)}\n"
        )

    def _normalize_vision_pillar(self, name: str, raw: Any) -> dict[str, Any]:
        base = raw if isinstance(raw, dict) else {"content": str(raw)}
        content = _ensure_min_words(str(base.get("content") or ""), name)
        return {
            "name": name,
            "purpose": str(base.get("purpose") or f"Define the purpose of the {name} pillar."),
            "good_end_state": str(base.get("good_end_state") or f"A strong long-term end state for {name}."),
            "failure_modes": _string_list(base.get("failure_modes")) or [f"{name} drifts into shallow activity without durable progress."],
            "relationships": _string_list(base.get("relationships")) or [f"{name} must reinforce the other pillars rather than compete with them."],
            "summary": str(base.get("summary") or f"Long-term direction for {name}."),
            "content": content,
        }

    def _block_from_json(self, parsed: dict[str, Any], *, block_id: int, planning_loop: int) -> BlockPlan:
        return BlockPlan(
            block_id=block_id,
            planning_loop=planning_loop,
            execution_range=(planning_loop + 1, planning_loop + 9),
            primary_pillar=str(parsed.get("primary_pillar") or "self"),
            why_this_pillar_now=str(parsed.get("why_this_pillar_now") or "The next block should make the strongest strategic move available."),
            target_outcomes=_string_list(parsed.get("target_outcomes")),
            sub_goals=_string_list(parsed.get("sub_goals")),
            allowed_support_work=_string_list(parsed.get("allowed_support_work")),
            explicit_non_goals=_string_list(parsed.get("explicit_non_goals")),
            success_signals=_string_list(parsed.get("success_signals")),
            failure_signals=_string_list(parsed.get("failure_signals")),
            expected_artifacts=_string_list(parsed.get("expected_artifacts")),
            metrics_to_watch=_string_list(parsed.get("metrics_to_watch")),
            risks=_string_list(parsed.get("risks")),
            review_focus=_string_list(parsed.get("review_focus")),
        )

    def _normalize_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": str(task.get("task_id") or "A"),
            "scope": str(task.get("scope") or "platform"),
            "objective": str(task.get("objective") or "Advance the active block with one coherent change."),
            "allowed_paths": [str(item) for item in (task.get("allowed_paths") or ["generations/"])],
            "success_signal": str(task.get("success_signal") or "A coherent repository change lands."),
            "priority": int(task.get("priority") or 1),
            "support_reason": str(task.get("support_reason") or "Supports the current block objective."),
        }

    def _test_vision(self, seed: str, loop_counter: int, current_version: int) -> LongTermVisionRecord:
        version = current_version + 1
        pillars = {
            "self": self._normalize_vision_pillar("self", {
                "purpose": "Turn Generations into a disciplined autonomous studio platform.",
                "good_end_state": "A reliable system that can plan, code, review, test, and explain its work coherently.",
                "failure_modes": ["It confuses activity for progress.", "It loses the thread between planning and execution."],
                "relationships": ["Self exists to make the game stronger.", "Self must support monetization with evidence rather than marketing fantasy."],
                "summary": "The platform must become a better autonomous builder.",
                "content": _vision_body("self", seed),
            }),
            "game": self._normalize_vision_pillar("game", {
                "purpose": "Build a distinctive transport and logistics game with systems depth.",
                "good_end_state": "A coherent playable prototype with enough originality and polish to plausibly target Steam.",
                "failure_modes": ["It remains a pile of design notes.", "It becomes a shallow prototype with no strategic identity."],
                "relationships": ["The game gives the platform a concrete proving ground.", "The game must earn any future monetization story."],
                "summary": "The game is the product proof and creative anchor.",
                "content": _vision_body("game", seed),
            }),
            "monetization_platform": self._normalize_vision_pillar("monetization_platform", {
                "purpose": "Create an honest public-facing commercial layer around the project.",
                "good_end_state": "A transparent support and launch surface that matches real progress and respects the audience.",
                "failure_modes": ["It appears before the product deserves it.", "It relies on vague hype or dark patterns."],
                "relationships": ["Monetization should amplify trust in the self pillar.", "Monetization should follow game proof rather than substitute for it."],
                "summary": "The monetization platform exists to support honest commercial ambition.",
                "content": _vision_body("monetization_platform", seed),
            }),
        }
        return LongTermVisionRecord(
            version=version,
            generated_at=now_iso(),
            refined_at_loop=loop_counter,
            index_summary="Generations exists to build itself into a better studio platform, prove that platform through a transport game, and only then earn trust commercially.",
            pillars=pillars,
            change_summary="Initial long-term vision created.",
        )

    def _test_initial_self_block(self, loop_counter: int) -> BlockPlan:
        return BlockPlan(
            block_id=1,
            planning_loop=loop_counter,
            execution_range=(2, 10),
            primary_pillar="self",
            why_this_pillar_now="The platform needs clearer planning, validation, and observability before larger game ambition becomes credible.",
            target_outcomes=["Make the platform more reliable.", "Make the website reflect block-level progress.", "Strengthen validation and operator visibility."],
            sub_goals=["Clarify planner outputs.", "Improve task execution reliability.", "Keep the journey page aligned with the active block."],
            allowed_support_work=["Website changes that explain self-platform progress.", "Active game seed artifacts that support future planning."],
            explicit_non_goals=["Do not start broad game implementation yet.", "Do not introduce monetization experiments beyond the placeholder disclosure."],
            success_signals=["The platform produces cleaner loop plans.", "The website explains block progress in human language.", "Validation remains reliable while the platform changes."],
            failure_signals=["Repeated no-op loops.", "Mixed-purpose loops with no strong block identity."],
            expected_artifacts=["Updated planner or runner code.", "Improved website summaries.", "Sharper operator debugging surfaces."],
            metrics_to_watch=["review_quality", "observability", "code_change"],
            risks=["Meta-work could expand without proving platform gains."],
            review_focus=["Did the platform become clearer and more reliable?"],
        )

    def _test_block(self, loop_counter: int, block_id: int) -> BlockPlan:
        primary = "game" if block_id >= 2 else "self"
        if block_id >= 10:
            primary = "monetization_platform"
        return BlockPlan(
            block_id=block_id,
            planning_loop=loop_counter,
            execution_range=(loop_counter + 1, loop_counter + 9),
            primary_pillar=primary,
            why_this_pillar_now=f"Block {block_id} should deepen the {primary} pillar based on the latest retrospective.",
            target_outcomes=[f"Advance {primary} in a coherent 9-loop chunk."],
            sub_goals=["Keep block work legible.", "Land artifacts that can be reviewed.", "Use support work only when it clearly helps the block."],
            allowed_support_work=["Platform support for the active block.", "Website explanation tied to the active block."],
            explicit_non_goals=["Do not change pillar mid-block without a planning loop."],
            success_signals=[f"The {primary} pillar becomes more concrete by the end of the block."],
            failure_signals=["Tasks scatter across unrelated scopes."],
            expected_artifacts=["Code, tests, docs, or website updates aligned to the block."],
            metrics_to_watch=["code_change", "balance", "review_quality"],
            risks=["The block could drift into vague maintenance."],
            review_focus=["Did each loop reinforce the chosen pillar?"],
        )

    def _test_retrospective(self, loop_counter: int, prior_block: dict[str, Any]) -> RetrospectiveRecord:
        return RetrospectiveRecord(
            block_id=int(prior_block["block_id"]),
            retrospective_loop=loop_counter,
            primary_pillar=str(prior_block["primary_pillar"]),
            execution_range=tuple(prior_block["execution_range"]),
            intended_outcomes=list(prior_block.get("target_outcomes") or []),
            actual_outcomes=["The block produced reviewable artifacts and sharper execution evidence."],
            wins=["The block stayed coherent."],
            failures=[],
            stalls=["Some loops rested instead of forcing a synthetic plan."],
            surprises=["Metrics were more useful as context than as commands."],
            metric_reflection={"helpful": ["review_quality", "code_change"], "misleading": ["balance when blocks were intentionally specialized"]},
            carry_forward=["Keep the next block equally focused."],
            change_next_time=["Choose the next pillar with stronger leverage."],
            summary="The previous block stayed coherent and revealed the next best chunk of work.",
        )

    def _test_loop(self, loop_counter: int, block_plan: dict[str, Any]) -> LoopPlan:
        primary = str(block_plan["primary_pillar"])
        tasks: list[ExecutionTask]
        if primary == "self":
            tasks = [
                ExecutionTask("A", "platform", "Tighten the planner or runner around the active block.", ["generations/src/generations", "generations/tests"], "The platform expresses the block more clearly in code and tests.", 1, "Direct self-platform work."),
                ExecutionTask("B", "platform", "Improve validation, memory, or operator visibility for the current block.", ["generations/src/generations", "generations/tests"], "Validation or observability becomes more legible.", 2, "Direct self-platform work."),
                ExecutionTask("C", "website", "Update the journey page so the block is legible to a human observer.", ["generations/src/generations/web"], "The public site explains the current block in human terms.", 3, "Website work supports the self pillar by improving observability."),
            ]
            budget = {"self": 0.7, "game": 0.15, "monetization_platform": 0.15}
        elif primary == "game":
            tasks = [
                ExecutionTask("A", "active_game", "Implement one small game-system artifact aligned to the active block.", ["games/active/src", "games/active/tests", "games/active/design"], "A concrete game artifact lands with supporting evidence.", 1, "Direct game work."),
                ExecutionTask("B", "active_game", "Add or refine tests and design notes for the current game step.", ["games/active/tests", "games/active/design", "games/active/src"], "The game step is better specified and checked.", 2, "Direct game work."),
                ExecutionTask("C", "platform", "Support the game block with a small platform improvement if needed.", ["generations/src/generations", "generations/tests"], "The platform better serves the active game loop.", 3, "Support work that helps game execution."),
            ]
            budget = {"self": 0.2, "game": 0.65, "monetization_platform": 0.15}
        else:
            tasks = [
                ExecutionTask("A", "website", "Improve support and disclosure surfaces with clearer honest copy.", ["generations/src/generations/web"], "The public monetization surface becomes clearer and more honest.", 1, "Direct monetization-platform work."),
                ExecutionTask("B", "website", "Record monetization experiments and intent more clearly on the website.", ["generations/src/generations/web"], "Monetization experiments are better explained and tracked.", 2, "Direct monetization-platform work."),
                ExecutionTask("C", "platform", "Add support tracking or validation for monetization changes.", ["generations/src/generations", "generations/tests"], "Monetization-platform work is better governed.", 3, "Support work that protects the monetization pillar."),
            ]
            budget = {"self": 0.15, "game": 0.15, "monetization_platform": 0.7}
        return LoopPlan(
            loop_counter=loop_counter,
            theme=f"Block {block_plan['block_id']} execution",
            goal=f"Advance the {primary} pillar coherently inside the active 9-loop block.",
            primary_pillar=primary,
            block_id=int(block_plan["block_id"]),
            planning_mode=False,
            block_plan_ref=int(block_plan["block_id"]),
            support_task_policy={"requires_justification": True},
            pillar_budget=budget,
            tasks=tasks,
            integration_policy={"merge_order": [task.task_id for task in tasks], "allow_partial_success": True},
            rationale="The execution loop should deepen the current block without switching pillars.",
        )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _pillar_budget(value: Any, primary: str) -> dict[str, float]:
    if isinstance(value, dict):
        normalized = {str(key): max(0.0, min(1.0, float(val))) for key, val in value.items()}
        if normalized:
            return normalized
    if primary == "self":
        return {"self": 0.7, "game": 0.15, "monetization_platform": 0.15}
    if primary == "game":
        return {"self": 0.2, "game": 0.65, "monetization_platform": 0.15}
    return {"self": 0.15, "game": 0.15, "monetization_platform": 0.7}


def _ensure_min_words(text: str, pillar: str) -> str:
    words = text.split()
    if len(words) >= 500:
        return text.strip()
    filler = (
        f"This {pillar} vision should remain specific, honest, and interconnected with the other pillars. "
        f"It should describe not only the destination but also the discipline required to keep Generations moving toward that destination without confusing motion for progress. "
        f"The point of this pillar is to sustain a long arc of work that can survive many loops, many revisions, and many local setbacks while still remaining legible to a human observer."
    )
    while len(words) < 500:
        words.extend(filler.split())
    return " ".join(words)


def _vision_body(pillar: str, seed: str) -> str:
    sentence = {
        "self": "The self pillar is about turning Generations into a better autonomous studio platform that can plan, code, review, test, observe itself, and explain its own choices clearly.",
        "game": "The game pillar is about turning the seed into a distinctive transport and logistics game with systems depth, a strong identity, and an executable path toward a plausible Steam release.",
        "monetization_platform": "The monetization platform pillar is about building an honest public surface that can support the project commercially without racing ahead of proof or trust.",
    }[pillar]
    base = f"Seed context: {seed}. {sentence} "
    return _ensure_min_words(base * 20, pillar)
