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

    def choose_next_step(self, seed: str, loop_count: int, memory: dict[str, object]) -> tuple[StepProposal, dict[str, object]]:
        try:
            proposal = self._choose_via_ollama(seed, loop_count, memory)
            metadata = self.metadata()
            metadata["fallback"] = None
            return proposal, metadata
        except Exception as exc:
            self.stubbed = True
            proposal = self._fallback_proposal(seed, loop_count, memory)
            metadata = self.metadata()
            metadata["fallback"] = f"{type(exc).__name__}: {exc}"
            return proposal, metadata

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

    def _prompt(self, seed: str, loop_count: int, memory: dict[str, object]) -> str:
        criteria = memory.get("criteria_history", [])[-1]
        heuristics = memory.get("heuristics", [])
        website_heuristics = memory.get("website_heuristics", [])
        monetization_heuristics = memory.get("monetization_heuristics", [])
        outcomes = memory.get("outcomes", {})
        return (
            "You are Generations.\n"
            "Your long-term mission is to autonomously improve this software system until it can manage the end-to-end "
            "development of a software project of its own choosing, with a strong bias toward creating games that could "
            "plausibly become Steam release candidates.\n"
            "You are not merely writing a game directly. You are improving the autonomous software, tooling, heuristics, "
            "evaluation criteria, observability, and website needed to eventually produce and ship a game.\n"
            "For this loop, decide one tiny safe next step.\n"
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
            f"Current heuristics: {json.dumps(heuristics, ensure_ascii=True)}\n"
            f"Current website heuristics: {json.dumps(website_heuristics, ensure_ascii=True)}\n"
            f"Current monetization heuristics: {json.dumps(monetization_heuristics, ensure_ascii=True)}\n"
            f"Recent outcomes: {json.dumps(outcomes, sort_keys=True)}\n"
            "First decide which workstream is better for this loop:\n"
            "- autonomous_platform: improve the self-improving software system itself\n"
            "- game_workspace: improve the current game workspace or game-production readiness\n"
            "Prefer autonomous_platform when core tooling, evaluation, observability, journaling, memory, or website foundations are still weak.\n"
            "Prefer game_workspace when the platform is stable enough to support a small, validated improvement to game readiness.\n"
            "Pick the smallest useful step that moves the system toward autonomous software development capability and eventual game production.\n"
        )

    def _fallback_proposal(self, seed: str, loop_count: int, memory: dict[str, object]) -> StepProposal:
        digest = hashlib.sha256(f"{seed}:{loop_count}".encode("utf-8")).hexdigest()[:12]
        heuristics = memory.get("heuristics", [])
        description = (
            "Refresh observability artifacts and keep the website aligned with the latest runtime state"
            if loop_count % 2 == 1
            else "Tighten the hello game pipeline and runtime narrative without expanding scope"
        )
        return StepProposal(
            workstream="autonomous_platform" if loop_count % 2 == 1 else "game_workspace",
            capability_target="website" if loop_count % 2 == 1 else "game_pipeline",
            description=description,
            rationale=(
                f"Deterministic fallback derived from seed digest {digest} and current heuristics count {len(heuristics)}. "
                "The chosen step prioritizes observability and software-system readiness before expanding direct game scope."
            ),
            target_files=[
                "README.md",
                "state/runtime.json",
                "games/hello_game/README.md",
            ],
            website_change=True,
            website_reason="Keep the journey page and exported site in sync with the latest autonomous state.",
            monetization_change=False,
            monetization_reason="No change; preserve the honest support placeholder until more evidence exists.",
            heuristics_updates=[
                "Prefer improvements that increase observability before increasing game complexity.",
            ],
        )

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stubbed": self.stubbed,
            "base_url": self.base_url,
            "selected_default_model": DEFAULT_MODEL,
            "todo": "If needed, swap local Ollama daemon access for a different Ollama Cloud endpoint via OLLAMA_BASE_URL.",
        }
