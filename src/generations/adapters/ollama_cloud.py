from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os

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
        self.stubbed = os.getenv("OLLAMA_CLOUD_API_KEY") in (None, "")

    def choose_next_step(self, seed: str, loop_count: int, memory: dict[str, object]) -> tuple[StepProposal, dict[str, object]]:
        digest = hashlib.sha256(f"{seed}:{loop_count}".encode("utf-8")).hexdigest()[:12]
        heuristics = memory.get("heuristics", [])
        description = (
            "Refresh observability artifacts and keep the website aligned with the latest runtime state"
            if loop_count % 2 == 1
            else "Tighten the hello game pipeline and runtime narrative without expanding scope"
        )
        proposal = StepProposal(
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
        return proposal, self.metadata()

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stubbed": self.stubbed,
            "selected_default_model": DEFAULT_MODEL,
            "todo": "Swap deterministic stub with real Ollama Cloud API calls when credentials are available.",
        }
