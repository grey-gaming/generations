"""Route cost calculation for the space logistics simulation."""

from typing import Dict, List
import math


def calculate_distance(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> float:
    """Calculate the Euclidean distance between two star systems.
    
    Args:
        x1, y1, z1: Coordinates of the first star system
        x2, y2, z2: Coordinates of the second star system
        
    Returns:
        Distance between the two star systems
    """
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def calculate_route_cost(distance: float, cargo_mass: float, fuel_price: float) -> float:
    """Calculate the cost of a route based on distance, cargo mass, and fuel price.
    
    Args:
        distance: Distance of the route in kilometers
        cargo_mass: Mass of cargo in tons
        fuel_price: Price of fuel per unit
        
    Returns:
        Total route cost
    """
    fuel_consumption_rate = 0.1
    fuel_cost = distance * fuel_consumption_rate * fuel_price
    handling_cost = cargo_mass * 0.05
    return fuel_cost + handling_cost
