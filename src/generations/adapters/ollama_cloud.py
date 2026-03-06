from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from urllib import error, request

from generations.config import DEFAULT_MODEL, DEFAULT_PROVIDER
from generations.models import StepProposal


@dataclass(slots=True)
class ModelResponse:
    content: str
    provider: str
    model: str
    stubbed: bool

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stubbed": self.stubbed,
        }


class OllamaCloudAdapter:
    def __init__(self) -> None:
        self.provider = os.getenv("GENERATIONS_MODEL_PROVIDER", DEFAULT_PROVIDER)
        self.model = os.getenv("GENERATIONS_MODEL", DEFAULT_MODEL)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.stubbed = False
        self.debug = os.getenv("GENERATIONS_DEBUG", "0") == "1"

    def choose_next_step(self, seed: str, loop_count: int, memory: dict[str, object]) -> tuple[StepProposal, dict[str, object]]:
        try:
            proposal = self._choose_via_ollama(seed, loop_count, memory)
            metadata = self.metadata()
            metadata["fallback"] = None
            if self.debug:
                metadata["prompt_preview"] = self._prompt(seed, loop_count, memory)[:1200]
            return proposal, metadata
        except Exception as exc:
            self.stubbed = True
            proposal = self._fallback_proposal(seed, loop_count, memory)
            metadata = self.metadata()
            metadata["fallback"] = f"{type(exc).__name__}: {exc}"
            if self.debug:
                metadata["prompt_preview"] = self._prompt(seed, loop_count, memory)[:1200]
            return proposal, metadata

    def plan_next_arc(
        self,
        seed: str,
        loop_count: int,
        recent_entries: list[dict[str, object]],
        memory: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        try:
            plan = self._plan_via_ollama(seed, loop_count, recent_entries, memory)
            metadata = self.metadata()
            metadata["fallback"] = None
            metadata["planning_call"] = True
            return plan, metadata
        except Exception as exc:
            self.stubbed = True
            plan = self._fallback_plan(seed, loop_count, recent_entries, memory)
            metadata = self.metadata()
            metadata["fallback"] = f"{type(exc).__name__}: {exc}"
            metadata["planning_call"] = True
            return plan, metadata

    def _choose_via_ollama(self, seed: str, loop_count: int, memory: dict[str, object]) -> StepProposal:
        prompt = self._prompt(seed, loop_count, memory)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }
        response_payload = self._post_json("/api/generate", payload)
        raw_response = response_payload.get("response", "").strip()
        parsed = json.loads(raw_response)
        return StepProposal(
            workstream=parsed["workstream"],
            capability_target=parsed["capability_target"],
            description=parsed["description"],
            rationale=parsed["rationale"],
            target_files=parsed["target_files"],
            website_change=bool(parsed["website_change"]),
            website_reason=parsed["website_reason"],
            monetization_change=bool(parsed["monetization_change"]),
            monetization_reason=parsed["monetization_reason"],
            heuristics_updates=list(parsed["heuristics_updates"]),
        )

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _plan_via_ollama(
        self,
        seed: str,
        loop_count: int,
        recent_entries: list[dict[str, object]],
        memory: dict[str, object],
    ) -> dict[str, object]:
        prompt = self._planning_prompt(seed, loop_count, recent_entries, memory)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }
        response_payload = self._post_json("/api/generate", payload)
        raw_response = response_payload.get("response", "").strip()
        parsed = json.loads(raw_response)
        return {
            "planning_loop": loop_count,
            "retrospective_summary": parsed["retrospective_summary"],
            "wins": list(parsed["wins"]),
            "mistakes": list(parsed["mistakes"]),
            "repeated_patterns": list(parsed["repeated_patterns"]),
            "next_chunk_theme": parsed["next_chunk_theme"],
            "next_chunk_goals": list(parsed["next_chunk_goals"]),
            "next_chunk_focus": list(parsed["next_chunk_focus"]),
            "risks": list(parsed["risks"]),
            "website_plan": parsed["website_plan"],
            "monetization_plan": parsed["monetization_plan"],
            "rationale": parsed["rationale"],
        }

    def _prompt(self, seed: str, loop_count: int, memory: dict[str, object]) -> str:
        criteria = memory.get("criteria_history", [])[-1]
        heuristics = memory.get("heuristics", [])
        heuristic_scores = memory.get("heuristics_rolling_average", {})
        website_heuristics = memory.get("website_heuristics", [])
        website_scores = memory.get("website_heuristics_rolling_average", {})
        monetization_heuristics = memory.get("monetization_heuristics", [])
        monetization_scores = memory.get("monetization_heuristics_rolling_average", {})
        outcomes = memory.get("outcomes", {})
        metrics = memory.get("evaluation_metrics", {})
        strategic_intent = memory.get("strategic_intent", {})
        planning = memory.get("planning", {}).get("current")
        return (
            "You are Generations.\n"
            "Your long-term mission is to autonomously improve this software system until it can manage the end-to-end "
            "development of a software project of its own choosing, with a strong bias toward creating games that could "
            "plausibly become Steam release candidates.\n"
            "You are not merely writing a game directly. You are improving the autonomous software, tooling, heuristics, "
            "evaluation criteria, observability, and website needed to eventually produce and ship a game.\n"
            "For this loop, decide one tiny safe next step.\n"
            "Think bigger than the next edit. You should reason in terms of multi-loop arcs such as:\n"
            "- evolving toward a distinctive game concept\n"
            "- building an economy or logistics simulation foundation\n"
            "- improving autonomous coding/review/testing capability\n"
            "- strengthening website trust and audience-building\n"
            "- preparing release-readiness criteria and production discipline\n"
            "The step itself must still be small, but it should clearly serve a bigger direction.\n"
            "The next step should improve at least one of:\n"
            "- autonomous software development capability\n"
            "- game-production readiness\n"
            "- evaluation/shipping criteria quality\n"
            "- journal or memory observability\n"
            "- journey website clarity, trust, or honest income potential\n"
            "You operate under these hard constraints:\n"
            "- Keep scope tiny, coherent, and reversible.\n"
            "- Prefer one small improvement over a broad rewrite.\n"
            "- Do not propose deceptive monetization, dark patterns, fake scarcity, secret exfiltration, or unsafe edits.\n"
            "- Favor steps that help the system become better at developing software that can eventually produce a game.\n"
            "- Treat the website as a first-class artifact that may evolve over time.\n"
            "- target_files must be a short list of relative repository paths.\n"
            "- target_files should prefer source files, docs, templates, or game workspace files; avoid generated state files, sqlite files, caches, and logs.\n"
            "Return JSON only. No markdown. No prose before or after JSON.\n"
            "Required JSON keys:\n"
            "- workstream: one of autonomous_platform or game_workspace\n"
            "- capability_target: one short label such as tooling, evaluation, memory, journaling, website, monetization, game_design, game_pipeline, game_prototype\n"
            "- description: short human-readable next step\n"
            "- rationale: why this tiny step helps Generations become a more capable autonomous software/game builder\n"
            "- target_files: array of relative paths\n"
            "- website_change: boolean\n"
            "- website_reason: short explanation\n"
            "- monetization_change: boolean\n"
            "- monetization_reason: short explanation\n"
            "- heuristics_updates: array of short heuristic statements, may be empty\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_count}\n"
            f"Current criteria: {json.dumps(criteria, sort_keys=True)}\n"
            f"Current heuristics: {json.dumps(self._weighted_heuristics(heuristics, heuristic_scores), ensure_ascii=True)}\n"
            f"Current website heuristics: {json.dumps(self._weighted_heuristics(website_heuristics, website_scores), ensure_ascii=True)}\n"
            f"Current monetization heuristics: {json.dumps(self._weighted_heuristics(monetization_heuristics, monetization_scores), ensure_ascii=True)}\n"
            f"Recent outcomes: {json.dumps(outcomes, sort_keys=True)}\n"
            f"Evaluation metrics: {json.dumps(metrics, sort_keys=True)}\n"
            f"Strategic intent: {json.dumps(strategic_intent, sort_keys=True)}\n"
            f"Current 10-loop plan: {json.dumps(planning, sort_keys=True) if planning else 'null'}\n"
            "First decide which workstream is better for this loop:\n"
            "- autonomous_platform: improve the self-improving software system itself\n"
            "- game_workspace: improve the current game workspace or game-production readiness\n"
            "Prefer autonomous_platform when core tooling, evaluation, observability, journaling, memory, or website foundations are still weak.\n"
            "Prefer game_workspace when the platform is stable enough to support a small, validated improvement to game readiness.\n"
            "Use past heuristics and evaluation metrics as guides, not as absolute rules.\n"
            "If recent code_change is low, prefer a real repository edit over pure state churn.\n"
            "If recent game_progress is low, bias toward game design, prototype, pipeline, or economy/system work.\n"
            "If recent creativity is low, prefer a step that adds a new mechanic, concept, tool, or framing rather than repeating the same maintenance action.\n"
            "If recent review_quality is low, strengthen tests, checks, or self-review before broadening scope.\n"
            "Avoid getting trapped in journaling-only or website-only loops unless observability is genuinely broken.\n"
            "If a current 10-loop plan exists, choose a step that advances that plan unless new evidence makes it clearly obsolete.\n"
            "When possible, choose a step that clarifies or advances the likely game direction, especially around transport, logistics, simulation, economy, progression, or player motivation.\n"
            "Pick the smallest useful step that moves the system toward autonomous software development capability and eventual game production.\n"
        )

    def _planning_prompt(
        self,
        seed: str,
        loop_count: int,
        recent_entries: list[dict[str, object]],
        memory: dict[str, object],
    ) -> str:
        return (
            "You are Generations.\n"
            "Every 10 completed loops, pause to run a planning phase.\n"
            "Review the last 10 loops, identify what is working, what is weak, and define a larger strategic chunk for the next 10 loops.\n"
            "Return JSON only.\n"
            "Required JSON keys:\n"
            "- retrospective_summary\n"
            "- wins: array of short bullets\n"
            "- mistakes: array of short bullets\n"
            "- repeated_patterns: array of short bullets\n"
            "- next_chunk_theme: short title\n"
            "- next_chunk_goals: array of short goals\n"
            "- next_chunk_focus: array of short focus areas\n"
            "- risks: array of short risks\n"
            "- website_plan: short sentence\n"
            "- monetization_plan: short sentence\n"
            "- rationale: short paragraph\n"
            f"Seed: {seed}\n"
            f"Completed loops so far: {loop_count}\n"
            f"Last 10 journal entries: {json.dumps(recent_entries, sort_keys=True)}\n"
            f"Current memory: {json.dumps(memory, sort_keys=True)}\n"
            "Bias toward larger coherent chunks, not isolated one-off edits.\n"
            "Use the retrospective to decide what the next chunk should optimize.\n"
        )

    def _weighted_heuristics(
        self,
        heuristics: list[object],
        scores: dict[str, object],
    ) -> list[dict[str, object]]:
        weighted: list[dict[str, object]] = []
        for item in heuristics:
            text = str(item)
            raw_score = scores.get(text, 0.0)
            try:
                score = round(float(raw_score), 2)
            except (TypeError, ValueError):
                score = 0.0
            weighted.append({"text": text, "rolling_average": score})
        return weighted

    def _fallback_proposal(self, seed: str, loop_count: int, memory: dict[str, object]) -> StepProposal:
        digest = hashlib.sha256(f"{seed}:{loop_count}".encode("utf-8")).hexdigest()[:12]
        heuristics = memory.get("heuristics", [])
        description = (
            "Refresh observability artifacts and keep the website aligned with the latest runtime state"
            if loop_count % 2 == 1
            else "Advance the space logistics game workspace toward a clearer design and build pipeline"
        )
        return StepProposal(
            workstream="autonomous_platform" if loop_count % 2 == 1 else "game_workspace",
            capability_target="website" if loop_count % 2 == 1 else "game_pipeline",
            description=description,
            rationale=(
                f"Deterministic fallback derived from seed digest {digest} and current heuristics count {len(heuristics)}. "
                "The chosen step prioritizes a larger development arc while keeping the individual change small and reversible."
            ),
            target_files=[
                "README.md",
                "games/space_logistics/README.md",
                "src/generations/web/templates/index.html",
            ],
            website_change=True,
            website_reason="Keep the journey page and exported site in sync with the latest autonomous state.",
            monetization_change=False,
            monetization_reason="No change; preserve the honest support placeholder until more evidence exists.",
            heuristics_updates=[
                "Prefer improvements that increase observability before increasing game complexity.",
            ],
        )

    def _fallback_plan(
        self,
        seed: str,
        loop_count: int,
        recent_entries: list[dict[str, object]],
        memory: dict[str, object],
    ) -> dict[str, object]:
        del seed, memory
        return {
            "planning_loop": loop_count,
            "retrospective_summary": f"Fallback planning pass over {len(recent_entries)} recent entries.",
            "wins": ["Validation and journaling remained intact across the recent chunk."],
            "mistakes": ["Some loops still favored observability or website work without enough meaningful repo change."],
            "repeated_patterns": ["Small documentation-heavy edits dominated the recent chunk."],
            "next_chunk_theme": "Turn recent design thinking into stronger repository changes",
            "next_chunk_goals": [
                "Land more meaningful source or game-workspace edits.",
                "Use each loop to serve a coherent larger arc.",
            ],
            "next_chunk_focus": [
                "game design",
                "game pipeline",
                "platform capability only when it unlocks the game arc",
            ],
            "risks": [
                "drifting into website-only loops",
                "inflating metrics without meaningful repo progress",
            ],
            "website_plan": "Keep the journey page aligned with the new chunk plan and retrospective.",
            "monetization_plan": "Do not expand monetization until the next chunk produces clearer product progress.",
            "rationale": "The next 10-loop chunk should convert recent reflection into more concrete autonomous game-building movement.",
        }

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stubbed": self.stubbed,
            "base_url": self.base_url,
            "selected_default_model": DEFAULT_MODEL,
            "todo": "If needed, swap local Ollama daemon access for a different Ollama Cloud endpoint via OLLAMA_BASE_URL.",
        }
