"""Route cost calculation for the space logistics simulation."""

from typing import Dict, List


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
