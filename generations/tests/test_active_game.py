from __future__ import annotations

import json
from pathlib import Path


def test_active_game_integration_map_exists() -> None:
    path = Path("games/active/design/integration_map.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["player_visible_state"] == []
    assert "cargo contracts" in data["missing_systems"]
