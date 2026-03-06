# Block 1 Plan

Planning loop: 1
Execution range: 2-10
Primary pillar: self

## Why This Pillar Now
Loop 0 established constitutional boundaries. Block 1 must instantiate the operational engine defined in the Self pillar. Without automated validation and persistent memory infrastructure in , subsequent game work risks accumulating technical debt and losing context across loops, violating the LTV mandate against amnesia and drift.

## Target Outcomes
- Enable automated rejection of untested code changes in via validation script
- Persist loop context state to disk for retrieval by subsequent loops without manual intervention
- Enable programmatic generation of journey status page from memory artifacts
- Enforce block planning schema programmatically before loop execution begins

## Sub Goals
- Scaffold directory structure for planning, validation, and observability
- Implement validate_loop script that exits non-zero on test failure
- Create journey_index.html generator that reads
- Define and validate Loop Plan JSON schema

## Allowed Support Work
- CI configuration for validation
- Basic CSS for journey_index.html within/

## Explicit Non Goals
- Game mechanics implementation
- Space logistics simulation logic
- Monetization integration
- Art asset creation
- / code changes

## Success Signals
- Validation script runs automatically on commit
- Journey page displays current loop number and status accurately
- Loop context file persists data across simulated restarts
- Block plan JSON passes schema validation

## Failure Signals
- Validation step skipped or bypassed
- Memory file corrupted or empty after loop
- Journey page shows stale or hardcoded data
- Plan schema errors detected during execution

## Expected Artifacts
- Describe the capability or artifact without naming repository paths.

## Metrics To Watch
- validation_pass_rate
- memory_retention_fidelity
- loop_completion_time
- artifact_generation_success

## Risks
- Over-engineering validation infrastructure before testing utility
- Getting stuck in infinite setup loops without producing artifacts
- Violating path constraints by creating forbidden directories

## Review Focus
- Does validation actually stop bad code?
- Is memory structure readable by human and machine?
- Are path constraints strictly obeyed?