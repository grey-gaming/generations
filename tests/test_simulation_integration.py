"""Integration tests for the unified simulation state and tick function."""

import pytest
from game.state import SimulationState, tick


class TestSimulationState:
    """Tests for the SimulationState dataclass."""

    def test_create_empty_state(self):
        """Test creating an empty simulation state."""
        state = SimulationState()
        assert state.turn == 0
        assert state.routes == []
        assert state.cargo_queue == []
        assert state.budget == 10000.0
        assert state.events == []

    def test_create_from_dict(self):
        """Test creating state from a dictionary."""
        data = {
            "turn": 5,
            "budget": 5000.0,
            "routes": [{"name": "A-B", "active": True}],
            "fuel_prices": {"base": 3.0}
        }
        state = SimulationState.from_dict(data)
        assert state.turn == 5
        assert state.budget == 5000.0
        assert len(state.routes) == 1
        assert state.fuel_prices["base"] == 3.0

    def test_to_dict(self):
        """Test converting state to dictionary."""
        state = SimulationState(turn=3, budget=7500.0)
        data = state.to_dict()
        assert data["turn"] == 3
        assert data["budget"] == 7500.0
        assert isinstance(data["routes"], list)

    def test_add_event(self):
        """Test adding events to state."""
        state = SimulationState()
        state.add_event("delivery", "Cargo delivered at B", {"cargo_id": 123})
        assert len(state.events) == 1
        assert state.events[0]["type"] == "delivery"
        assert state.events[0]["data"]["cargo_id"] == 123


class TestTickFunction:
    """Tests for the tick() orchestration function."""

    def test_tick_increments_turn(self):
        """Test that tick increments the turn counter."""
        state = SimulationState(turn=0)
        tick(state)
        assert state.turn == 1
        tick(state)
        assert state.turn == 2

    def test_tick_processes_active_route(self):
        """Test that tick processes an active route."""
        route = {
            "name": "A-B",
            "active": True,
            "origin": "A",
            "travel_time": 2,
            "progress": 0,
            "cargo_capacity": 10,
            "fuel_consumption": 1.0
        }
        state = SimulationState(routes=[route], cargo_queue=[{"origin": "A"}])
        tick(state)
        assert state.routes[0]["status"] == "in_transit"
        assert state.routes[0]["progress"] == 1

    def test_tick_applies_fuel_costs(self):
        """Test that tick applies fuel costs to budget."""
        route = {
            "name": "A-B",
            "active": True,
            "origin": "A",
            "travel_time": 1,
            "progress": 0,
            "fuel_consumption": 2.0
        }
        state = SimulationState(
            routes=[route],
            cargo_queue=[{"origin": "A"}],
            fuel_prices={"base": 3.0},
            budget=10000.0
        )
        tick(state)
        assert state.budget < 10000.0

    def test_tick_records_fuel_event(self):
        """Test that tick records fuel cost events."""
        route = {
            "name": "A-B",
            "active": True,
            "origin": "A",
            "travel_time": 1,
            "progress": 0,
            "fuel_consumption": 1.0
        }
        state = SimulationState(
            routes=[route],
            cargo_queue=[{"origin": "A"}],
            fuel_prices={"base": 2.5}
        )
        tick(state)
        fuel_events = [e for e in state.events if e["type"] == "fuel_cost"]
        assert len(fuel_events) > 0

    def test_tick_empty_state(self):
        """Test that tick handles empty state gracefully."""
        state = SimulationState()
        tick(state)
        assert state.turn == 1
        assert state.events == []
