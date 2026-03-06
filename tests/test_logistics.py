"""Tests for logistics calculation functions."""

import pytest
from workspace.game.logistics import calculate_route_cost
from workspace.game.schemas import Route, CargoType, Cargo


class TestCalculateRouteCost:
    """Tests for the calculate_route_cost function."""

    def test_basic_route_cost(self):
        """Test cost calculation for a basic route."""
        route = Route(
            name="Test Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=100.0
        )
        cost = calculate_route_cost(route)
        assert cost == 100.0

    def test_long_distance_route(self):
        """Test cost for a longer distance route."""
        route = Route(
            name="Long Route",
            origin="Earth",
            destination="Mars",
            distance=225000000.0,
            travel_time=2592000.0,
            cargo_capacity=1000.0
        )
        cost = calculate_route_cost(route)
        # capacity_factor = 1.0 / (1000/100) = 0.1
        # cost = 225000000 * 0.1 = 22500000.0
        assert cost == 22500000.0

    def test_high_capacity_route(self):
        """Test that high capacity routes have lower cost per distance."""
        low_capacity_route = Route(
            name="Small Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=50.0
        )
        high_capacity_route = Route(
            name="Large Route",
            origin="A",
            destination="B",
            distance=100.0,
            travel_time=10.0,
            cargo_capacity=200.0
        )
        low_cost = calculate_route_cost(low_capacity_route)
        high_cost = calculate_route_cost(high_capacity_route)
        # Higher capacity should mean lower cost (economies of scale)
        assert high_cost < low_cost

    def test_cost_scales_with_distance(self):
        """Test that cost scales linearly with distance."""
        route1 = Route(
            name="Short",
            origin="A",
            destination="B",
            distance=50.0,
            travel_time=5.0,
            cargo_capacity=100.0
        )
        route2 = Route(
            name="Long",
            origin="A",
            destination="B",
            distance=150.0,
            travel_time=15.0,
            cargo_capacity=100.0
        )
        cost1 = calculate_route_cost(route1)
        cost2 = calculate_route_cost(route2)
        assert cost2 == cost1 * 3
