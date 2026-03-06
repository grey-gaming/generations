"""Simulation runner for the logistics game pipeline."""


def run_simulation_tick(state: dict) -> dict:
    """Execute one tick of the simulation pipeline.
    
    Processes the pickup-transport-delivery sequence for all active routes.
    
    Args:
        state: Current simulation state containing routes, cargo, and economy data
        
    Returns:
        Updated simulation state after processing one tick
    """
    routes = state.get("routes", [])
    cargo_queue = state.get("cargo_queue", [])
    
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
    
    return state
