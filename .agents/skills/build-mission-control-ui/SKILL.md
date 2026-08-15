---
name: build-mission-control-ui
description: Build or modify ExoSwarm's mission-control frontend and scientific storytelling UI. Use for light-curve/periodogram/transit visualizations, investigation timelines, agent/tool states, evidence boards, hypothesis displays, result locking, catalog reveal, loading/error states, and demo-facing interactions. Success means the UI reflects real investigation state clearly and passes the relevant frontend/build checks. Do not use for backend-only logic or numerical astronomy implementation.
---

# Build Mission Control UI

## Preserve the information hierarchy

- Prioritize:
  1. target and investigation status,
  2. core scientific visualization,
  3. current hypothesis and strongest alternative,
  4. active agent or reviewer action,
  5. scientific tool being executed,
  6. evidence returned,
  7. hypothesis update,
  8. result-lock and catalog-reveal state.
- Keep scientific plots more prominent than agent prose.
- Avoid chatbot-first layouts and generic dashboard-card sprawl.

## Bind visuals to real state

- Drive every major visual transition from an actual investigation event or backend state.
- Show real tool names, measured values, statuses, and evidence.
- Avoid fabricated terminal output, fake progress, and invented scientific values.
- Keep the frontend a renderer of investigation state rather than a second source of scientific truth.

## Make agent activity concise

- Display:
  - selected experiment,
  - short reason,
  - tool status,
  - evidence returned,
  - next branch.
- Avoid long persona conversations.
- Do not expose hidden chain-of-thought.

## Build around the demo narrative

- Support a sequence such as:
  1. real TESS target loaded,
  2. raw or normalized light curve shown,
  3. periodic candidate detected,
  4. period evidence shown,
  5. phase-folded transit shown,
  6. skeptic identifies an unresolved alternative,
  7. additional diagnostic runs,
  8. evidence board updates,
  9. verdict locks,
  10. catalog ground truth reveals.
- Keep the flow understandable to a judge without astronomy expertise.

## Show evidence rather than invented confidence

- Display explicit diagnostics with units or significance when available.
- Separate measured evidence from interpretation.
- Prefer a disposition such as "candidate survives implemented vetting tests" over an unexplained AI probability.
- Display statistical probabilities only when a defined statistical model produced them.

## Protect the reveal

- Keep ground-truth values hidden until the backend confirms result lock.
- Display lock state unambiguously.
- Display a run identifier, timestamp, or hash when the backend provides one.
- Prevent frontend shortcuts from bypassing the lock.

## Handle latency and failure honestly

- Show real loading states for actual model or scientific-tool work.
- Show explicit states for:
  - data unavailable,
  - scientific-tool failure,
  - model timeout,
  - ambiguous evidence,
  - rejected signal,
  - insufficient evidence.
- Preserve the investigation experience when one non-critical step fails.

## Preserve visual consistency

- Inspect existing components, typography, spacing, plotting conventions, motion, and design tokens before adding new UI.
- Reuse existing primitives.
- Use animation to explain state transitions, not decorate static content.

## Verify the UI

- Run the relevant frontend tests.
- Run the production build.
- Exercise loading, failure, locked, and reveal states.
- Verify charts receive real structured values.
- Verify no placeholder scientific values remain.
- Test at the expected hackathon demo viewport.
