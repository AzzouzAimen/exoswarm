---
name: verify-integration
description: Verify ExoSwarm behavior end to end across scientific tools, structured evidence, investigation state, agent decisions, backend events/APIs, and frontend rendering. Use after a cross-layer change or when individual components pass but the complete flow is uncertain. Success means one representative success path and one relevant failure path are traced across every changed boundary with schema, unit, ordering, and lock invariants checked. Do not use instead of root-cause debugging when a concrete failure is already known.
---

# Verify Integration

## Map the changed path

- Identify every producer-consumer boundary touched by the change.
- Record for each boundary:
  - producer,
  - schema or type,
  - consumer,
  - serialization or transport,
  - error behavior.
- Distinguish matching field names from matching semantics.

## Check contracts

- Inspect common integration hazards:
  - renamed fields,
  - optional versus required values,
  - enum mismatch,
  - numeric strings versus numbers,
  - null handling,
  - time formats,
  - stale state,
  - duplicate events,
  - missing target or run identifiers,
  - unit mismatch.
- Treat scientific unit mismatch as a correctness failure even when the UI looks plausible.

## Trace one representative success case

- Use a cached demo fixture when available.
- Trace:
  1. input load,
  2. deterministic scientific call,
  3. exact structured result,
  4. investigation-state update,
  5. agent evidence input,
  6. next-action selection,
  7. backend event or API output,
  8. frontend state update,
  9. final visualization.
- Capture enough intermediate evidence to identify the first divergent layer.

## Trace one relevant failure case

- Exercise at least one likely failure such as:
  - scientific-tool failure,
  - missing data,
  - model timeout,
  - invalid agent action,
  - schema validation failure,
  - attempted catalog access while locked.
- Verify the failure remains explicit through every layer.

## Check investigation invariants

- Deny ground-truth access before result lock.
- Reject unknown or malformed tool actions.
- Prevent failed tool results from becoming successful evidence.
- Prevent stale results from attaching to another target or run.
- Ensure the verdict references evidence from the same investigation.

## Check asynchronous ordering

- Verify ordering, duplication, and final state for streamed or queued events.
- Verify idempotency or duplicate protection when implemented.
- Verify reconnect or refresh behavior when relevant.
- Prevent impossible intermediate states from becoming final UI state.

## Run layered checks

- Run narrow schema and unit tests first.
- Run relevant science, backend, and frontend tests.
- Run type checks and builds that cover the changed path.
- Run a full smoke path after narrower checks pass.

## Report the integration result

- State the exact end-to-end path tested.
- State the target or fixture used.
- List the commands or checks run.
- State failures found and fixed.
- State any unverified boundary.
