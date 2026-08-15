---
name: orchestrate-investigation
description: Implement or modify ExoSwarm's runtime scientific-agent investigation loop, including hypothesis state, bounded experiment selection, tool permissions, model routing/escalation, evidence updates, audit records, and stopping rules. Use when changing how agents decide which scientific action happens next. Success means different evidence can cause different valid branches while deterministic tools remain numerical authority and catalog ground truth stays locked. Do not use to implement the numerical astronomy algorithms themselves.
---

# Orchestrate Investigation

## Keep investigation state structured

- Store, as applicable:
  - target and run identifiers,
  - observation quality,
  - active hypotheses,
  - collected evidence,
  - completed tests,
  - available tests,
  - strongest unresolved alternative,
  - current disposition,
  - step count,
  - ground-truth lock state.
- Do not rely on conversational prose as the only source of truth.

## Bound the action space

- Register the scientific actions the agent may select.
- Validate tool names and parameters before execution.
- Reject unknown actions.
- Include explicit stop actions.
- Keep mandatory safety checks separate from agent-selected follow-up experiments.

## Separate measurement from interpretation

- Let the agent:
  - identify leading and alternative hypotheses,
  - choose a discriminating experiment,
  - give a concise reason,
  - interpret structured evidence,
  - decide whether to continue or stop.
- Let deterministic tools:
  - compute measurements,
  - attach units and significance,
  - return diagnostics and provenance,
  - fail explicitly.
- Never let the agent invent missing measurements.

## Require evidence-dependent branching

- Make realistic evidence produce different next actions.
- Prefer branches such as:
  - odd-even anomaly -> investigate eclipsing-binary explanations,
  - bright nearby source -> prioritize centroid or contamination checks,
  - unstable low-SNR period -> test preprocessing or cross-sector consistency,
  - strong clean evidence -> stop instead of running every available tool.
- Reconsider any step whose exact next tool could always be chosen at compile time.

## Require structured decisions

- Use the repository's existing decision schema when available.
- Include at least:
  - leading hypothesis,
  - strongest alternative,
  - selected next action,
  - concise reason,
  - expected discriminating outcome.
- Validate the decision before tool execution.
- Persist the validated decision rather than free-form hidden reasoning.

## Route models deliberately

- Keep model and provider choices configurable.
- Use the faster or cheaper model for routine bounded decisions.
- Escalate to a stronger model only on an inspectable condition such as:
  - conflicting evidence,
  - low controller confidence about action selection,
  - repeated invalid action output,
  - final adversarial review.
- Keep escalation unable to access hidden ground truth.

## Bound the loop

- Define maximum steps, retry limits, and terminal states.
- Support terminal outcomes such as:
  - candidate survives implemented vetting,
  - planetary interpretation rejected,
  - insufficient evidence,
  - investigation failed.
- Stop when additional available tests have low value or the configured evidence requirement is satisfied.
- Prevent infinite tool loops.

## Preserve auditability

- Persist:
  - evidence visible to the decision model,
  - selected action,
  - concise reason,
  - model/controller identity,
  - tool result,
  - resulting state update.
- Do not expose or persist hidden chain-of-thought as a product feature.

## Test branching and safety

- Add scenario tests for:
  - clean planet-like evidence,
  - eclipsing-binary-like evidence,
  - contamination-like evidence,
  - weak/noisy evidence.
- Assert that at least some scenarios select different valid next actions.
- Test invalid actions, malformed structured output, model timeout, maximum-step stopping, and denied pre-lock ground-truth access.

## Verify completion

- Confirm actions are bounded and validated.
- Confirm different evidence can produce different branches.
- Confirm deterministic tools remain numerical authority.
- Confirm decisions are auditable.
- Confirm stopping is bounded.
- Confirm catalog blinding cannot be bypassed.
