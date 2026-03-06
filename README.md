# Generations

Generations is an autonomous Ubuntu-first game-development platform.

Repository layout:
- `generations/`: platform code, planner, executor, journal, memory, web, validation
- `games/hello_game/`: tiny stable sample game
- `games/active/`: active game workspace
- `state/`: runtime state and debug artifacts
- `site/`: exported local-first journey site

Core commands:
- `generations run --seed "..."`
- `generations web --host 127.0.0.1 --port 8000`
- `generations status`
- `generations pause`
- `generations resume`
- `generations export-web --out ./site`

Development:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

Configure OpenCode for the local Ollama model and launch the runner:
```bash
./scripts/configure-opencode-and-run.sh "Build a space transport and logistics web game"
```

Run the slower end-to-end smoke test explicitly:
```bash
pytest -m slow generations/tests/test_smoke.py
```
