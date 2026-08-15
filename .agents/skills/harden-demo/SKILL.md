---
name: harden-demo
description: Harden the finished ExoSwarm hackathon demo for repeatability, timing, cached/offline operation, reset behavior, model/API failure recovery, and blind result-lock integrity. Use only after the core scientific and agent flows work and the priority is making the exact judged 3-minute path reliable. Success means the primary demo completes from a clean reset at least three consecutive times with valid science and ground truth locked until reveal. Do not use to add speculative features or compensate for unproven core science.
---

# Harden Demo

## Freeze the judged path

- Identify the exact primary target, optional false-positive target, demo route, scientific tools, model calls, visual states, and final reveal.
- Treat features outside that path as lower priority.
- Stop adding scope unless a change directly removes a demo blocker.

## Remove live-data fragility

- Cache the required real inputs and metadata locally when appropriate.
- Prepare known-good fallbacks for external services used in the judged path.
- Prefer rerunning deterministic scientific computation from cached real inputs.
- Never fabricate a scientific result when a live service fails.

## Protect blind ground truth

- Deny investigation access to hidden catalog parameters.
- Persist the predicted result before unlock.
- Require an explicit unlock transition.
- Tie the reveal to the locked run.
- Restore the locked state on demo reset.
- Preserve a run identifier, timestamp, or hash when available.

## Bound model failure

- Validate structured model output.
- Set practical timeouts.
- Cap retries.
- Reject unknown actions and invalid parameters.
- Preserve the last valid investigation state after a model failure.
- Make stronger-model escalation depend on an inspectable runtime condition rather than a demo-only switch.

## Make reset deterministic

- Provide one documented reset action or script.
- Restore:
  - the expected target,
  - clean investigation state,
  - locked ground truth,
  - required caches,
  - expected service state,
  - no stale events.
- Test reset repeatedly.

## Time the exact sequence

- Measure:
  - startup,
  - investigation,
  - slowest scientific or model call,
  - time to result lock,
  - reveal,
  - total judged sequence.
- Keep meaningful headroom under the time limit.

## Rehearse failure recovery

- Test the judged environment with:
  - no network,
  - one model timeout,
  - one external API failure,
  - frontend refresh,
  - backend restart when practical,
  - a non-critical scientific-tool failure.
- Record the fastest safe recovery action.

## Require repeatability

- Complete the primary demo from a clean reset at least three consecutive times.
- Verify each run:
  - uses the intended real input data,
  - produces scientifically consistent outputs,
  - follows a valid agent branch,
  - reaches the final disposition,
  - locks the result,
  - keeps catalog truth inaccessible until unlock,
  - reveals ground truth for the same locked run.

## Produce a readiness result

- Report PASS or FAIL for:
  - clean startup,
  - cached inputs,
  - science pipeline,
  - adaptive agent branch,
  - model routing,
  - result lock,
  - catalog reveal,
  - frontend build,
  - total demo runtime.
- List blockers and the tested recovery procedure.
