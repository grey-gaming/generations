"""Tests for economy invariants in the logistics simulation."""

import pytest
from workspace.game.schemas import Cargo, CargoType, Route


class TestEconomyInvariants:
    """Tests for basic economy invariants."""

    def test_cargo_quantity_positive(self):
        """Test that cargo quantity must always be positive."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            Cargo(
                cargo_type=CargoType.FOOD,
                quantity=0,
                origin="A",
                destination="B"
            )

    def test_cargo_priority_bounds(self):
        """Test that cargo priority must be between 1 and 5."""
        with pytest.raises(ValueError, match="Priority must be between 1 and 5"):
            Cargo(
                cargo_type=CargoType.FOOD,
                quantity=10.0,
                origin="A",
                destination="B",
                priority=6
            )

    def test_route_distance_positive(self):
        """Test that route distance must always be positive."""
        with pytest.raises(ValueError, match="Distance must be positive"):
            Route(
                name="Invalid Route",
                origin="A",
                destination="B",
                distance=0,
                travel_time=10.0,
                cargo_capacity=100.0
            )

    def test_route_capacity_positive(self):
        """Test that route cargo capacity must always be positive."""
        with pytest.raises(ValueError, match="Cargo capacity must be positive"):
            Route(
                name="Invalid Route",
                origin="A",
                destination="B",
                distance=100.0,
                travel_time=10.0,
                cargo_capacity=0
            )
