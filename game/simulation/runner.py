"""Simulation runner for the logistics game pipeline."""

from typing import TYPE_CHECKING, Union, Dict, Any

if TYPE_CHECKING:
    from ..state import SimulationState


def run_simulation_tick(state: Union[Dict[str, Any], "SimulationState"]) -> Dict[str, Any]:
    """Execute one tick of the simulation pipeline.
    
    Processes the pickup-transport-delivery sequence for all active routes.
    
    Args:
        state: Current simulation state containing routes, cargo, and economy data
        
    Returns:
        Updated simulation state after processing one tick
    """
    from ..state import SimulationState
    
    if isinstance(state, SimulationState):
        state_dict = state.to_dict()
    else:
        state_dict = state
    
    routes = state_dict.get("routes", [])
    cargo_queue = state_dict.get("cargo_queue", [])
    
    for route in routes:
        if route.get("active", False):
            pending = [c for c in cargo_queue if c["origin"] == route["origin"]]
            if pending:
                route["status"] = "loading"
                loaded = min(len(pending), int(route.get("cargo_capacity", 1)))
                route["status"] = "in_transit"
                route["progress"] = route.get("progress", 0) + 1
                if route["progress"] >= route.get("travel_time", 1):
                    route["status"] = "delivered"
                    route["progress"] = 0
    
    if isinstance(state, SimulationState):
        state.routes = routes
        state.cargo_queue = cargo_queue
    
    return state_dict
