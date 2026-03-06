"""Unit tests for route cost calculation."""

import unittest
from src.routes import calculate_route_cost, calculate_distance, calculate_fuel_cost


class TestDistanceCalculation(unittest.TestCase):
    """Test cases for the calculate_distance function."""

    def test_distance_same_point(self):
        """Test distance calculation when both points are the same."""
        distance = calculate_distance(1.0, 2.0, 3.0, 1.0, 2.0, 3.0)
        self.assertEqual(distance, 0.0)

    def test_distance_basic(self):
        """Test basic distance calculation between two points."""
        distance = calculate_distance(0.0, 0.0, 0.0, 3.0, 4.0, 0.0)
        self.assertEqual(distance, 5.0)


class TestFuelCostCalculation(unittest.TestCase):
    """Test cases for the calculate_fuel_cost function."""

    def test_basic_fuel_cost(self):
        """Test basic fuel cost calculation."""
        cost = calculate_fuel_cost(distance=100.0, fuel_price=2.0)
        expected = 100.0 * 0.1 * 2.0
        self.assertEqual(cost, expected)

    def test_fuel_cost_custom_consumption(self):
        """Test fuel cost with custom consumption rate."""
        cost = calculate_fuel_cost(distance=100.0, fuel_price=2.0, consumption_rate=0.2)
        expected = 100.0 * 0.2 * 2.0
        self.assertEqual(cost, expected)

    def test_zero_fuel_cost(self):
        """Test fuel cost with zero distance."""
        cost = calculate_fuel_cost(distance=0.0, fuel_price=2.0)
        self.assertEqual(cost, 0.0)


class TestRouteCostCalculation(unittest.TestCase):
    """Test cases for the calculate_route_cost function."""

    def test_basic_route_cost(self):
        """Test basic route cost calculation."""
        cost = calculate_route_cost(distance=100.0, cargo_mass=50.0, fuel_price=2.0)
        expected = (100.0 * 0.1 * 2.0) + (50.0 * 0.05)
        self.assertEqual(cost, expected)

    def test_zero_distance(self):
        """Test route with zero distance."""
        cost = calculate_route_cost(distance=0.0, cargo_mass=50.0, fuel_price=2.0)
        expected = 50.0 * 0.05
        self.assertEqual(cost, expected)

    def test_zero_cargo(self):
        """Test route with zero cargo mass."""
        cost = calculate_route_cost(distance=100.0, cargo_mass=0.0, fuel_price=2.0)
        expected = 100.0 * 0.1 * 2.0
        self.assertEqual(cost, expected)


if __name__ == '__main__':
    unittest.main()
