from __future__ import annotations

from generations.adapters.ollama_cloud import OllamaCloudAdapter
from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.models import PlanningRecord
from generations.planning.store import PlanningStore
from generations.state import now_iso


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
        updated = dict(memory)
        planning = dict(updated.get("planning", {"current": None, "history": []}))
        planning["current"] = record.as_dict()
        planning["history"] = (list(planning.get("history", [])) + [record.as_dict()])[-5:]
        updated["planning"] = planning
        updated["pillar_state"] = {
            pillar: {
                "trajectory": details["trajectory"],
                "confidence": details["confidence"],
            }
            for pillar, details in record.pillar_assessment.items()
        }
        self.memory.replace(updated, created_at=now_iso())
        self.store.write(runtime_loop_count, {**record.as_dict(), "model_provider": metadata})
        self.journal.append(
            {
                "timestamp": now_iso(),
                "loop_counter": runtime_loop_count,
                "entry_type": "planning_phase",
                "planning": record.as_dict(),
                "model_provider": metadata,
            }
        )
        return record
