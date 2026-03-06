"""Core data schemas for the logistics simulation game."""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class CargoType(Enum):
    """Types of cargo that can be transported."""
    RAW_MATERIALS = "raw_materials"
    MANUFACTURED_GOODS = "manufactured_goods"
    FOOD = "food"
    FUEL = "fuel"
    EQUIPMENT = "equipment"


@dataclass
class Cargo:
    """Represents a shipment of cargo."""
    cargo_type: CargoType
    quantity: float
    origin: str
    destination: str
    owner: Optional[str] = None
    priority: int = 1

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.priority < 1 or self.priority > 5:
            raise ValueError("Priority must be between 1 and 5")


@dataclass
class Route:
    """Represents a transport route between locations."""
    name: str
    origin: str
    destination: str
    distance: float
    travel_time: float
    cargo_capacity: float
    active: bool = True
    cargo_list: List[Cargo] = field(default_factory=list)

    def __post_init__(self):
        if self.distance <= 0:
            raise ValueError("Distance must be positive")
        if self.travel_time <= 0:
            raise ValueError("Travel time must be positive")
        if self.cargo_capacity <= 0:
            raise ValueError("Cargo capacity must be positive")

    def add_cargo(self, cargo: Cargo) -> bool:
        """Add cargo to the route if capacity allows."""
        total_cargo = sum(c.quantity for c in self.cargo_list)
        if total_cargo + cargo.quantity <= self.cargo_capacity:
            self.cargo_list.append(cargo)
            return True
        return False

    def remove_cargo(self, cargo: Cargo) -> bool:
        """Remove cargo from the route."""
        if cargo in self.cargo_list:
            self.cargo_list.remove(cargo)
            return True
        return False

    @property
    def current_load(self) -> float:
        """Calculate current cargo load on the route."""
        return sum(c.quantity for c in self.cargo_list)

    @property
    def available_capacity(self) -> float:
        """Calculate remaining cargo capacity."""
        return self.cargo_capacity - self.current_load
