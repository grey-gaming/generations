from __future__ import annotations

from typing import Any

from generations.adapters.ollama_cloud import OllamaCloudAdapter
from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.models import PlanningRecord
from generations.planning.store import PlanningStore
from generations.state import now_iso

PILLARS = ["game", "self", "website", "tidiness"]


class Planner:
    def __init__(self, config: AppConfig, model: OllamaCloudAdapter, journal: JournalStore, memory: MemoryStore) -> None:
        self.config = config
        self.model = model
        self.journal = journal
        self.memory = memory
        self.store = PlanningStore(config.planning_dir)

    def ensure_checkpoint(self, seed: str, runtime_loop_count: int) -> PlanningRecord:
        memory = self.memory.latest()
        existing = memory.get("planning", {}).get("current")
        if existing and runtime_loop_count % 10 != 0:
            return PlanningRecord(**existing)
        if existing and int(existing.get("planning_loop", -1)) == runtime_loop_count:
            return PlanningRecord(**existing)
        recent_entries = self.journal.tail(20)
        record, metadata = self.model.plan_checkpoint(seed, runtime_loop_count, memory, recent_entries)
        normalized_record = self._normalize_record(record)
        updated = dict(memory)
        planning = dict(updated.get("planning", {"current": None, "history": []}))
        planning["current"] = normalized_record.as_dict()
        planning["history"] = (list(planning.get("history", [])) + [normalized_record.as_dict()])[-5:]
        updated["planning"] = planning
        updated["pillar_state"] = {
            pillar: {
                "trajectory": details["trajectory"],
                "confidence": details["confidence"],
            }
            for pillar, details in normalized_record.pillar_assessment.items()
        }
        self.memory.replace(updated, created_at=now_iso())
        self.store.write(runtime_loop_count, {**normalized_record.as_dict(), "model_provider": metadata})
        self.journal.append(
            {
                "timestamp": now_iso(),
                "loop_counter": runtime_loop_count,
                "entry_type": "planning_phase",
                "planning": normalized_record.as_dict(),
                "model_provider": metadata,
            }
        )
        return normalized_record

    def _normalize_record(self, record: PlanningRecord) -> PlanningRecord:
        normalized_assessment: dict[str, dict[str, Any]] = {}
        for pillar in PILLARS:
            raw = record.pillar_assessment.get(pillar, {})
            normalized_assessment[pillar] = self._normalize_pillar_details(raw)
        record.pillar_assessment = normalized_assessment
        return record

    def _normalize_pillar_details(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            trajectory = raw.get("trajectory", "unclear")
            if trajectory not in {"on_track", "unclear", "off_track"}:
                trajectory = "unclear"
            confidence = raw.get("confidence", 0.5)
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                confidence_value = 0.5
            return {
                "current_state": str(raw.get("current_state", "Assessment unavailable.")),
                "trajectory": trajectory,
                "biggest_risk": str(raw.get("biggest_risk", "Assessment unavailable.")),
                "confidence": max(0.0, min(1.0, confidence_value)),
            }
        if isinstance(raw, str):
            return {
                "current_state": raw,
                "trajectory": "unclear",
                "biggest_risk": "Assessment needs structure.",
                "confidence": 0.4,
            }
        return {
            "current_state": "Assessment unavailable.",
            "trajectory": "unclear",
            "biggest_risk": "Assessment unavailable.",
            "confidence": 0.5,
        }
