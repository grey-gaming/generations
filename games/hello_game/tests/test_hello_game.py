from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.hello_game.main import run_turn


def test_hello_game_turn_reports_delivery() -> None:
    result = run_turn()
    assert result["cargo"] == "medical supplies"
    assert result["profit"] == 12
