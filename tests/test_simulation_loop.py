"""Tests for the simulation loop runner."""

import pytest
from game.simulation.runner import run_simulation_tick


class TestSimulationTick:
    """Tests for the simulation tick execution."""

    def test_empty_state_returns_empty(self):
        """Test that an empty state returns an empty state."""
        state = {}
        result = run_simulation_tick(state)
        assert result == {}

    def test_inactive_route_not_processed(self):
        """Test that inactive routes are not processed."""
        state = {
            "routes": [{"name": "A-B", "active": False, "origin": "A"}],
            "cargo_queue": [{"origin": "A", "destination": "B"}]
        }
        result = run_simulation_tick(state)
        assert result["routes"][0].get("status") is None

    def test_active_route_processes_cargo(self):
        """Test that active routes process cargo from their origin."""
        state = {
            "routes": [{
                "name": "A-B",
                "active": True,
                "origin": "A",
                "travel_time": 2,
                "progress": 0,
                "cargo_capacity": 10
            }],
            "cargo_queue": [{"origin": "A", "destination": "B"}]
        }
        result = run_simulation_tick(state)
        assert result["routes"][0]["status"] == "in_transit"
        assert result["routes"][0]["progress"] == 1

    def test_route_completes_delivery(self):
        """Test that routes complete delivery when progress reaches travel_time."""
        state = {
            "routes": [{
                "name": "A-B",
                "active": True,
                "origin": "A",
                "travel_time": 1,
                "progress": 1,
                "cargo_capacity": 10
            }],
            "cargo_queue": [{"origin": "A", "destination": "B"}]
        }
        result = run_simulation_tick(state)
        assert result["routes"][0]["status"] == "delivered"
        assert result["routes"][0]["progress"] == 0
