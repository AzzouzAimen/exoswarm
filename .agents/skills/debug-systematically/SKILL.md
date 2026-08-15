---
name: debug-systematically
description: Diagnose and fix bugs, failing tests, build failures, performance regressions, and unexpected ExoSwarm behavior by finding the root cause before editing. Use whenever the task is primarily troubleshooting an existing failure, especially across multiple layers. Success means the failure is reproduced or evidenced, one root-cause hypothesis is tested at a time, the smallest root fix is made, and a regression check passes. Do not use for new feature implementation or planned refactors without a concrete failure.
---

# Debug Systematically

## Reproduce or collect evidence

- Read the complete error, stack trace, logs, and failing assertion.
- Reproduce the issue consistently when possible.
- Record the smallest reliable reproduction.
- If reproduction is intermittent, gather observations instead of guessing.

## Locate the failing boundary

- Inspect recent relevant changes.
- Trace the actual data or control flow through affected components.
- Add temporary diagnostic instrumentation when a multi-layer system hides the failing boundary.
- Compare values entering and leaving each relevant layer.
- Identify the earliest point where actual behavior diverges from expected behavior.

## Compare with a working path

- Find a similar working implementation or passing test when one exists.
- Compare configuration, inputs, dependencies, schemas, environment, and state.
- List meaningful differences before proposing a fix.
- Avoid assuming that a small difference cannot matter.

## Form one hypothesis

- State one specific root-cause hypothesis and the evidence supporting it.
- Design the smallest experiment that can confirm or reject that hypothesis.
- Change one variable at a time.
- If the hypothesis fails, return to evidence gathering and form a new hypothesis.
- Do not stack speculative fixes.

## Fix the root cause

- Add a failing regression test or minimal reproducible check when practical.
- Make the smallest change that addresses the identified cause.
- Avoid unrelated cleanup and refactoring during the fix.
- Remove temporary instrumentation that is no longer needed.

## Verify the fix

- Run the regression check that failed before.
- Run nearby tests likely to catch collateral damage.
- Exercise the original user-visible failure path when practical.
- Confirm that the observed symptom and the identified cause are both resolved.

## Escalate architecture concerns

- Stop repeated patching if several well-tested hypotheses fail or each attempted fix exposes a different coupling problem.
- Reassess the architecture instead of attempting another speculative patch.
- Explain the evidence before proposing a larger redesign.

## Report the diagnosis

- State the root cause.
- State the evidence that established it.
- State the fix.
- State the regression check.
- State any remaining uncertainty.
