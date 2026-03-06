# Space Logistics

`space_logistics` is the current seed game workspace.

It exists to give Generations a concrete destination: a transport and logistics game with economy, routing, progression, and world simulation.

## Design Direction

Core pillars:
- Route optimization across star systems
- Resource extraction, refinement, and delivery contracts
- Fleet management with upgrade paths
- Dynamic economy influenced by player actions

## Build Pipeline

Completed:
1. Define core data models (ships, routes, commodities) - `game/state.py`
2. Implement economy simulation tick - `game/state.py:tick()`

Next steps:
3. Build terminal UI prototype
4. Add save/load system
5. Define ship upgrade mechanics

The goal is not to stay a placeholder forever. The autonomous loop should gradually turn this workspace into a clearer design, then a prototype, then a more credible game candidate.
