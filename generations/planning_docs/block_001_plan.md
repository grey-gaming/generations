# Block 1 Plan

Planning loop: 1
Execution range: 2-10
Primary pillar: self

## Why This Pillar Now
Loop 0 defined the strategic vision; Block 1 must establish the operational engine (validation, memory, observability) to ensure subsequent game development loops are disciplined, observable, and trustworthy before any game logic is committed.

## Target Outcomes
- Automated validation pipeline prevents invalid memory state commits.
- Public journey page renders current status from memory.
- Planning module successfully decomposes block goals into loop tasks.
- Memory schema enforces structure on all execution logs.

## Sub Goals
- Implement pre-commit hook for memory schema validation.
- Build static site generator for journey page within generations root.
- Create loop closure script that updates memory and triggers site build.
- Define metric collection interface for observability.

## Allowed Support Work
- Repository scaffolding for directory.
- CI configuration for validation scripts.
- Documentation of the block planning protocol.

## Explicit Non Goals
- Game mechanics implementation.
- Art asset creation.
- Monetization integration.
- Physics simulation logic.

## Success Signals
- Validation script returns non-zero exit code on invalid JSON.
- Journey page updates within 5 minutes of loop closure.
- Memory file grows linearly with loop count.
- Block plan remains stable throughout 9 loops.

## Failure Signals
- Manual bypass of validation hooks.
- Journey page displays stale Loop 0 data.
- Memory schema drifts without version increment.
- Sub-goals remain unstarted after Loop 3.

## Expected Artifacts
- Describe the capability or artifact without naming repository paths.

## Metrics To Watch
- validation_pass_rate
- loop_closure_latency
- memory_write_success
- site_build_duration

## Risks
- Over-engineering validation logic delaying execution.
- Site styling distractions consuming loop capacity.
- Memory schema becoming too rigid for future game data.

## Review Focus
- Does the validation actually protect integrity? Is the journey page honest about failures? Is the memory schema extensible?