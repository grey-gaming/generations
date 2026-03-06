"""Turn dataclass for the logistics game pipeline."""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Turn:
    """Encapsulates one cycle of logistics and economy updates.
    
    A Turn represents a complete cycle through:
    1. Pickup phase - cargo loading at origins
    2. Transit phase - movement along routes
    3. Delivery phase - cargo unloading at destinations
    4. Economy update - market price and cost adjustments
    """
    turn_number: int = 0
    phase: str = "pickup"
    routes: List[Dict[str, Any]] = field(default_factory=list)
    cargo_queue: List[Dict[str, Any]] = field(default_factory=list)
    economy_state: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    def next_phase(self) -> str:
        """Advance to the next phase in the turn cycle."""
        phase_order = ["pickup", "transit", "delivery", "economy"]
        current_idx = phase_order.index(self.phase) if self.phase in phase_order else -1
        next_idx = (current_idx + 1) % len(phase_order)
        self.phase = phase_order[next_idx]
        return self.phase
    
    def start_new_turn(self) -> None:
        """Increment turn number and reset to pickup phase."""
        self.turn_number += 1
        self.phase = "pickup"
        self.events = []
