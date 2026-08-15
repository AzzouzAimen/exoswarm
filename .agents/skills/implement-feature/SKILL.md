---
name: implement-feature
description: Implement a non-trivial ExoSwarm feature from contract through verified code when no narrower skill owns the task. Use for general backend, frontend, state, API, or cross-layer feature work requiring multiple edits and tests. Success means the smallest coherent implementation is complete and relevant checks pass. Do not use for bugs, deterministic astronomy methods, mission-control UI work, investigation orchestration, integration-only verification, or demo hardening; use the narrower skill instead.
---

# Implement Feature

## Inspect the existing path

- Read the relevant code before editing.
- Identify the requested behavior, existing implementation path, affected interfaces, and relevant tests.
- Reuse an existing abstraction when it fits.
- Avoid parallel implementations and unrelated refactors.

## Define the contract

- Specify the expected inputs, outputs, state changes, errors, and acceptance criteria.
- Identify any schema, API, event, or persistence changes.
- Keep the contract as small as the requested feature allows.
- Preserve existing compatibility unless the task explicitly requires a breaking change.

## Plan a short implementation

- Write roughly 3-8 verifiable steps.
- Prefer this order when applicable:
  1. contract or schema,
  2. failing test or fixture,
  3. minimal implementation,
  4. integration,
  5. verification.
- Keep each step independently inspectable.
- Avoid speculative architecture work.

## Implement incrementally

- Make one coherent change at a time.
- Run the narrowest relevant test after each meaningful step.
- Inspect failures before making another change.
- Keep deterministic science, agent policy, backend orchestration, and UI responsibilities separated.

## Verify the feature

- Run the repository's relevant unit tests.
- Run type checks, linting, formatting checks, builds, or smoke tests that cover the changed path.
- Inspect the repository for the correct commands instead of inventing commands.
- Verify failure behavior, not only the happy path.
- Remove temporary debug code and accidental placeholder data.

## Report completion

- State what changed.
- State which interfaces or files changed materially.
- List the exact verification performed.
- State any remaining limitation or unverified path.
- Do not claim completion without verification evidence.
