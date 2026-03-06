"""State dataclass for the logistics game simulation."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class SimulationState:
    """Unified state container for the logistics simulation.
    
    Encapsulates all mutable state required for one tick of the simulation:
    - Routes: active transport paths with progress tracking
    - Cargo: items waiting or in transit
    - Economy: market prices, fuel costs, and operational expenses
    """
    turn: int = 0
    routes: List[Dict[str, Any]] = field(default_factory=list)
    cargo_queue: List[Dict[str, Any]] = field(default_factory=list)
    fuel_prices: Dict[str, float] = field(default_factory=dict)
    economy_state: Dict[str, Any] = field(default_factory=dict)
    budget: float = 10000.0
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationState":
        """Create a SimulationState from a dictionary."""
        return cls(
            turn=data.get("turn", 0),
            routes=data.get("routes", []),
            cargo_queue=data.get("cargo_queue", []),
            fuel_prices=data.get("fuel_prices", {}),
            economy_state=data.get("economy_state", {}),
            budget=data.get("budget", 10000.0),
            events=data.get("events", [])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a dictionary for serialization."""
        return {
            "turn": self.turn,
            "routes": self.routes,
            "cargo_queue": self.cargo_queue,
            "fuel_prices": self.fuel_prices,
            "economy_state": self.economy_state,
            "budget": self.budget,
            "events": self.events
        }
    
    def add_event(self, event_type: str, description: str, data: Optional[Dict] = None) -> None:
        """Add an event to the state for this tick."""
        event = {
            "type": event_type,
            "description": description,
            "data": data or {}
        }
        self.events.append(event)


def tick(state: SimulationState) -> SimulationState:
    """Execute one tick of the simulation pipeline.
    
    Orchestrates route, fuel, and economy updates in sequence:
    1. Process active routes (pickup -> transit -> deliver)
    2. Update fuel consumption and costs
    3. Adjust economy prices based on market conditions
    
    Args:
        state: Current simulation state
        
    Returns:
        Updated simulation state after one tick
    """
    from game.simulation.runner import run_simulation_tick
    
    state.turn += 1
    
    run_simulation_tick(state)
    
    _apply_fuel_costs(state)
    
    _update_economy(state)
    
    return state


def _apply_fuel_costs(state: SimulationState) -> None:
    """Apply fuel costs for active routes."""
    total_fuel_cost = 0.0
    base_fuel_price = state.fuel_prices.get("base", 2.5)
    
    for route in state.routes:
        if route.get("active", False):
            fuel_consumption = route.get("fuel_consumption", 1.0)
            route_fuel_cost = base_fuel_price * fuel_consumption
            total_fuel_cost += route_fuel_cost
    
    state.budget -= total_fuel_cost
    if total_fuel_cost > 0:
        state.add_event("fuel_cost", f"Paid ${total_fuel_cost:.2f} in fuel costs")


def _update_economy(state: SimulationState) -> None:
    """Apply economy adjustments and market price updates."""
    # Simple economy adjustment - prices fluctuate slightly each tick
    demand_modifier = state.economy_state.get("demand_modifier", 1.0)
    for cargo in state.cargo_queue:
        base_value = cargo.get("base_value", 100)
        cargo["current_value"] = base_value * demand_modifier
