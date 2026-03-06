# Journal Schema

Journal entries are newline-delimited JSON stored in `state/journal.jsonl`.

## Required Fields

- `loop_counter`: Integer identifying the loop number.
- `timestamp`: ISO 8601 timestamp of entry creation.
- `commit_hash`: Git commit hash for this loop.
- `seed_hash`: Seed hash used for deterministic decision making.
- `validation_summary`: One of `passed`, `failed`, `not run`.

## Optional Fields

- `strategic_question_addressed`: String describing the strategic question this loop addressed. Used for transparency and alignment tracking.
- `next_step`: Object describing the next recommended action.
- `evaluation_metrics`: Object with numeric scores for various autonomy metrics.
- `monetization_change`: Object describing any monetization experiment changes.
- `website_change`: Object describing any website changes.
- `opencode`: Object with OpenCode session metadata.
- `rest_decision`: Object describing the rest/continue decision.
- `validation_results`: Array of validation command results.
- `actions_taken`: Array of file paths modified in this loop.
- `criteria`: Snapshot of current criteria at time of entry.
