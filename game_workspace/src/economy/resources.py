"""Core resource data structures for the space logistics economy."""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class ResourceType(Enum):
    """Categories of resources in the space economy."""
    RAW_MATERIAL = "raw_material"
    COMPONENT = "component"
    CONSUMABLE = "consumable"
    ENERGY = "energy"


@dataclass
class Resource:
    """Definition of a resource type in the economy."""
    id: str
    name: str
    resource_type: ResourceType
    base_price: float
    mass: float
    volume: float
    description: Optional[str] = None


@dataclass
class ResourceQuantity:
    """A quantity of a specific resource."""
    resource_id: str
    amount: float

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Resource amount cannot be negative")
