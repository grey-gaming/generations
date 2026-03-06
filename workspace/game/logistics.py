"""Logistics calculation functions for the space logistics simulation."""

from .schemas import Route, CargoType


def calculate_route_cost(route: Route) -> float:
    """Calculate the base cost for a route.
    
    Cost is calculated based on distance and cargo capacity.
    Larger capacity routes have economies of scale.
    
    Args:
        route: The route to calculate cost for.
        
    Returns:
        The base cost for operating this route.
    """
    capacity_factor = 1.0 / (route.cargo_capacity / 100.0)
    return route.distance * capacity_factor
