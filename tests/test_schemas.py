"""Tests for the logistics simulation schemas."""

import pytest
from workspace.game.schemas import Cargo, Route, CargoType


class TestCargo:
    """Tests for the Cargo dataclass."""

    def test_create_cargo(self):
        """Test creating a basic cargo instance."""
        cargo = Cargo(
            cargo_type=CargoType.FUEL,
            quantity=100.0,
            origin="Station A",
            destination="Station B"
        )
        assert cargo.cargo_type == CargoType.FUEL
        assert cargo.quantity == 100.0
        assert cargo.origin == "Station A"
        assert cargo.destination == "Station B"
        assert cargo.priority == 1

    def test_cargo_with_owner(self):
        """Test creating cargo with an owner."""
        cargo = Cargo(
            cargo_type=CargoType.FOOD,
            quantity=50.0,
            origin="Farm",
            destination="City",
            owner="Merchant Guild"
        )
        assert cargo.owner == "Merchant Guild"

    def test_cargo_custom_priority(self):
        """Test creating cargo with custom priority."""
        cargo = Cargo(
            cargo_type=CargoType.EQUIPMENT,
            quantity=25.0,
            origin="Factory",
            destination="Base",
            priority=5
        )
        assert cargo.priority == 5

    def test_invalid_quantity(self):
        """Test that negative quantity raises error."""
        with pytest.raises(ValueError):
            Cargo(
                cargo_type=CargoType.FUEL,
                quantity=-10.0,
                origin="A",
                destination="B"
            )

    def test_zero_quantity(self):
        """Test that zero quantity raises error."""
        with pytest.raises(ValueError):
            Cargo(
                cargo_type=CargoType.FUEL,
                quantity=0,
                origin="A",
                destination="B"
            )

    def test_invalid_priority_low(self):
        """Test that priority < 1 raises error."""
        with pytest.raises(ValueError):
            Cargo(
                cargo_type=CargoType.FUEL,
                quantity=10.0,
                origin="A",
                destination="B",
                priority=0
            )

    def test_invalid_priority_high(self):
        """Test that priority > 5 raises error."""
        with pytest.raises(ValueError):
            Cargo(
                cargo_type=CargoType.FUEL,
                quantity=10.0,
                origin="A",
                destination="B",
                priority=6
            )


class TestRoute:
    """Tests for the Route dataclass."""

    def test_create_route(self):
        """Test creating a basic route instance."""
        route = Route(
            name="Alpha Route",
            origin="Earth",
            destination="Mars",
            distance=225000000.0,
            travel_time=2592000.0,
            cargo_capacity=1000.0
        )
        assert route.name == "Alpha Route"
        assert route.distance == 225000000.0
        assert route.cargo_capacity == 1000.0
        assert route.active is True
        assert len(route.cargo_list) == 0

    def test_add_cargo(self):
        """Test adding cargo to a route."""
        route = Route(
            name="Test Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=100.0
        )
        cargo = Cargo(
            cargo_type=CargoType.FUEL,
            quantity=50.0,
            origin="A",
            destination="B"
        )
        assert route.add_cargo(cargo) is True
        assert len(route.cargo_list) == 1
        assert route.current_load == 50.0

    def test_add_cargo_exceeds_capacity(self):
        """Test that adding too much cargo fails."""
        route = Route(
            name="Test Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=100.0
        )
        cargo1 = Cargo(
            cargo_type=CargoType.FUEL,
            quantity=80.0,
            origin="A",
            destination="B"
        )
        cargo2 = Cargo(
            cargo_type=CargoType.FOOD,
            quantity=50.0,
            origin="A",
            destination="B"
        )
        assert route.add_cargo(cargo1) is True
        assert route.add_cargo(cargo2) is False
        assert len(route.cargo_list) == 1

    def test_remove_cargo(self):
        """Test removing cargo from a route."""
        route = Route(
            name="Test Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=100.0
        )
        cargo = Cargo(
            cargo_type=CargoType.FUEL,
            quantity=50.0,
            origin="A",
            destination="B"
        )
        route.add_cargo(cargo)
        assert route.remove_cargo(cargo) is True
        assert len(route.cargo_list) == 0

    def test_remove_cargo_not_present(self):
        """Test removing cargo that isn't on the route."""
        route = Route(
            name="Test Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=100.0
        )
        cargo = Cargo(
            cargo_type=CargoType.FUEL,
            quantity=50.0,
            origin="A",
            destination="B"
        )
        assert route.remove_cargo(cargo) is False

    def test_available_capacity(self):
        """Test calculating available capacity."""
        route = Route(
            name="Test Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=100.0
        )
        cargo = Cargo(
            cargo_type=CargoType.FUEL,
            quantity=30.0,
            origin="A",
            destination="B"
        )
        route.add_cargo(cargo)
        assert route.available_capacity == 70.0

    def test_invalid_distance(self):
        """Test that negative distance raises error."""
        with pytest.raises(ValueError):
            Route(
                name="Bad Route",
                origin="A",
                destination="B",
                distance=-100.0,
                travel_time=10.0,
                cargo_capacity=100.0
            )

    def test_invalid_travel_time(self):
        """Test that negative travel time raises error."""
        with pytest.raises(ValueError):
            Route(
                name="Bad Route",
                origin="A",
                destination="B",
                distance=100.0,
                travel_time=-10.0,
                cargo_capacity=100.0
            )

    def test_invalid_capacity(self):
        """Test that negative capacity raises error."""
        with pytest.raises(ValueError):
            Route(
                name="Bad Route",
                origin="A",
                destination="B",
                distance=100.0,
                travel_time=10.0,
                cargo_capacity=-100.0
            )
