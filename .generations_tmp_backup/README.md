# Generations

Generations is a minimal Ubuntu-first autonomous codebase that can run locally, maintain a visible journal and memory, serve a journey website, and self-modify through a local OpenCode-style workflow.

## What Exists In This Seed

- Python 3.11+ package under `src/generations`
- CLI commands:
  - `generations run --seed "..."`
  - `generations web --host 127.0.0.1 --port 8000`
  - `generations status`
  - `generations pause`
  - `generations resume`
  - `generations export-web --out ./site/`
- Append-only journal in `state/journal.jsonl`
- Queryable memory snapshots in `state/memory.sqlite3`
- Local journey website rendered from on-disk artifacts
- `games/hello_game/` seed game workspace
- OpenCode adapter stub with `plan -> apply -> verify -> commit`
- Ollama Cloud adapter stub with required default model `qwen3.5:397b-cloud`

## Ubuntu Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## Run The Autonomous Loop

```bash
generations run --seed "Build yourself into a capable autonomous game studio"
```

Behavior:
- Runs until Generations decides to stop under its current criteria.
- Current bootstrap criteria intentionally stop after a few validated tiny loops in normal mode.
- `Ctrl+C` is handled gracefully: the current step finishes safely, journal and runtime state are flushed, and the process exits.
- `state/pause.flag` is checked between loops.

Operational-only safety valve:
- `GENERATIONS_MAX_LOOPS=<n>` limits loop count for operator safety only.
- This is not the definition of done.
- Default is no limit.

Test harness only:
- `GENERATIONS_TEST_MODE=1` forces exactly one safe loop, then stop.
- This exists only so automated tests stay fast and deterministic.
- It must not be used to define done in normal operation.

## Web Journey

Start the local web server:

```bash
generations web --host 127.0.0.1 --port 8000
```

Endpoints:
- `/` human-readable journey page
- `/journal` JSON journal feed
- `/memory` JSON memory snapshot
- `/status` JSON runtime status

Export a static copy:

```bash
generations export-web --out ./site
```

## Journal And Memory

Every loop writes a journal entry with:
- timestamp and loop counter
- seed hash
- current criteria version and content
- chosen next step
- files touched
- validation results
- commit hash
- model/provider metadata
- rest decision
- website change summary
- monetization change summary

Memory snapshots store:
- current criteria version
- outcomes summary
- evolving heuristics
- website heuristics
- monetization heuristics
- monetization experiments log
- tool routing summary

## Website And Monetization Evolution Rules

Implemented baseline:
- local-first journey page works offline from disk state
- support panel is present but intentionally minimal and honest
- disclosure panel explains that monetization may evolve and all changes are logged
- monetization experiments are stored in memory and journaled

Guardrails:
- no deceptive UI
- no fake scarcity
- no dark patterns
- no intrusive tracking by default
- sponsorships/affiliates/analytics must be labeled, reversible, and validated

The runner treats website changes as first-class artifacts and records their intent each loop.

## Self-Modification Guardrails

All autonomous edits go through the OpenCode adapter interface only.

Current local adapter behavior:
1. produce a plan
2. apply a small change
3. run validation
4. create one small commit if validation passes

If validation fails, the loop stops and the failure is journaled. The adapter boundary is the intended swap point for a real OpenCode integration later.

Validation behavior:
- preferred: `pytest` smoke/unit checks
- fallback when `pytest` is not installed: `python -m compileall src tests games`
- failed validation triggers rollback of expected touched files before the loop journals the failure

## Real Integration Swap Points

### OpenCode

Current file: `src/generations/adapters/opencode.py`

Replace the local subprocess workflow with real OpenCode API calls while preserving the adapter interface consumed by `runner.py`.

### Ollama Cloud

Current file: `src/generations/adapters/ollama_cloud.py`

Default metadata always names:
- provider: `ollama_cloud`
- model: `qwen3.5:397b-cloud`

When credentials are available, replace the deterministic proposal stub with real Ollama Cloud requests without changing the caller contract.

## Tests

- `tests/test_smoke.py`: temp-repo smoke test that runs one safe loop and confirms journal, memory, and exported site are written
- `tests/test_journal.py`: append-only journal behavior

## Notes

- Ubuntu-only assumptions: bash, git, standard Linux filesystem paths.
- The initial seed is intentionally conservative: it proves the autonomous operating loop, observability surface, and safe self-edit path before pursuing larger game scope.
