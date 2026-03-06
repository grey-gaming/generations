from __future__ import annotations


def run_turn() -> dict[str, object]:
    state = {
        "vehicle": "shuttle",
        "cargo": "medical supplies",
        "origin": "Depot",
        "destination": "Station Alpha",
        "profit": 12,
        "status": "delivered",
    }
    print(f"{state['vehicle']} delivered {state['cargo']} to {state['destination']} for {state['profit']} credits")
    return state


if __name__ == "__main__":
    run_turn()
