"""Logistics calculation functions for the space logistics simulation."""

from typing import Dict, Tuple
from .schemas import Route, CargoType


def calculate_route_distance(origin_coords: Tuple[float, float], destination_coords: Tuple[float, float]) -> float:
    """Calculate the Euclidean distance between two points.
    
    Args:
        origin_coords: (x, y) coordinates of the origin.
        destination_coords: (x, y) coordinates of the destination.
        
    Returns:
        The distance between the two points.
    """
    dx = destination_coords[0] - origin_coords[0]
    dy = destination_coords[1] - origin_coords[1]
    return (dx ** 2 + dy ** 2) ** 0.5


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
