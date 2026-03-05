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
        return (
            "You are Generations, an autonomous game-studio bootstrapper.\n"
            "Decide one tiny safe next step for the current loop.\n"
            "Return JSON only with keys: description, rationale, target_files, website_change, website_reason, "
            "monetization_change, monetization_reason, heuristics_updates.\n"
            "Constraints:\n"
            "- Keep scope tiny and reversible.\n"
            "- Prefer observability, website clarity, and small game progress.\n"
            "- Do not propose deceptive monetization.\n"
            "- target_files must be a short list of relative paths.\n"
            f"Seed: {seed}\n"
            f"Loop: {loop_count}\n"
            f"Current criteria: {json.dumps(criteria, sort_keys=True)}\n"
            f"Current heuristics: {json.dumps(heuristics, ensure_ascii=True)}\n"
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
            description=description,
            rationale=f"Deterministic stub proposal derived from seed digest {digest} and current heuristics count {len(heuristics)}.",
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
