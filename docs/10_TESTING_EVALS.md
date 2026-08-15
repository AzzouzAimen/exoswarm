# Testing, Evaluation, and Release Gates

## Layered verification

Use the narrowest test first, then broaden:

1. schema/unit tests,
2. deterministic science tests,
3. agent-policy tests over synthetic/curated evidence states,
4. backend API/event tests,
5. frontend type/lint/build tests,
6. end-to-end success/failure smoke paths,
7. demo repeatability checks.

Avoid requiring live astronomy APIs for regression tests.

## Scaffold-level tests

The initial repository should include at least:

- `test_schema_contracts.py`
- `test_tool_registry.py`
- `test_blind_protocol.py`
- `test_result_lock.py`
- `test_api_smoke.py`

Critical assertions:

- unknown actions are rejected,
- reveal is denied before lock,
- agent code cannot import reveal/ground-truth implementation,
- required schema fields are enforced,
- terminal reason exists for terminal state,
- run/action/event IDs exist,
- scientific results require status/provenance,
- unsupported ground-truth fields do not appear in pre-lock state/events.

## Scientific validation ladder

When a science tool is implemented:

1. controlled synthetic/deterministic fixture,
2. cached real TESS target if relevant,
3. integration regression for schema/unit propagation.

Set expected values/ranges and tolerances before evaluating a new result. Include positive, negative, and indeterminate cases. Test fragile units explicitly: days vs hours, fraction vs percent vs ppm, epoch conventions, radius ratio vs depth, sign/sigma conventions.

## Final-stretch agent evaluation suite

Keep a locked three-case minimum suite for the submission:

- one clean planet-like/confirmed-planet holdout,
- one eclipsing-binary-like false positive,
- one deliberately difficult/inconclusive case.

Run the suite after meaningful harness/inference changes. Keep deterministic unit fixtures for
additional failure classes. Once all submission gates are green, add a fourth contamination/spatial
case only if it validates the centroid path or improves the visible demo; do not pursue case count
for its own sake. Do not optimize the agent for one demo star.

## Deterministic graders

Useful PASS/FAIL checks include:

- catalog access never occurs before `RESULT_LOCKED`,
- recognizable target identity never enters agent context before reveal,
- a measurable candidate is recovered when expected,
- period error is within a declared target tolerance when ground truth is later available,
- mandatory tests are completed,
- scientifically different cases take different valid branches,
- known false-positive cases avoid a strong planetary disposition,
- an inconclusive case remains inconclusive when appropriate,
- no agent invents a numerical measurement without evidence reference,
- maximum turn/tool budgets are respected,
- tool schemas are valid.

Grade outcomes and constraints, not one hard-coded trajectory.

## Branch-diversity tests

At minimum, test evidence states representing:

- clean planet-like evidence,
- eclipsing-binary-like evidence,
- weak/noisy or contamination-like evidence.

Assert that at least some cases select different valid next actions. If every path is predetermined, the behavior belongs in a workflow, not the agent.

## Explicit final-stretch cuts

Do not build the agent-vs-fixed-policy ablation or the `pass^3` stochastic metric for the hackathon
submission. Retain ordinary deterministic regression checks, branch tests, and the three-case
minimum suite; a gated fourth high-value spatial case is allowed.
Release repeatability below is operational demo hardening, not an inference-consistency metric.

## Provider and structured-output canary

Run 10 repetitions of the two-role canary (20 decisions total) across its five bounded evidence
states. Record model identity, finish reasons, latency, input/output tokens, first-attempt schema
and semantic validity, repairs, fallback count, and errors. Require at least 90% first-attempt
validity and 100% validity after the one repair policy, with no provider error/timeout and no raw
light-curve samples. Also require at least 80% evidence-specific decision quality and at least
three distinct resolved action branches across the five states. Reports must include timestamp,
commit, prompt versions, sanitized configuration, and a configuration fingerprint. The canary is
integration evidence; it must not mutate the locked three-case evaluator.

The credential-independent three-target gate is
`apps/api/tests/test_cached_backend_gate.py`. The live scientific boundary gate is
`scripts/run_live_backend_gate.py`; it must reach both agent roles through FastAPI, expose SSE and
safe artifact metadata, lock the result, and verify the reveal against the exact locked hash.

### Evaluator-integrity regression note

Do not treat every low Critic score as a Critic or prompt defect. During the 2026-08-15 canary
hardening, the Skeptic selected the expected action in 10/10 cases, but the initial aggregate
decision-quality score was 12/20 because the canary supplied the Critic with a generic proposal
whose purpose was only to exercise the response schema. The Critic correctly vetoed or revised
that proposal because it was not tied to the state's strongest unresolved alternative. The fix was
to make each evaluation proposal scientifically relevant to its evidence state, hypothesis, and
expected discriminating result—not to weaken the Critic, its review prompt, or the acceptance
rubric.

Likewise, when the live gate selected unavailable `centroid_localization`, retain the controller's
strict rejection. The structural fix was `agent-context-v3`, which omits unavailable and previously
executed actions from model affordances while leaving the full registry in deterministic audit and
enforcement code. Before changing prompts or agent policy after an eval failure, inspect the exact
fixture proposal, model-visible action set, and deterministic expected outcome. Preserve the tests
that require relevant Critic proposals and omission of unavailable actions.

## Release/demo gate

After the core works, the judged path should complete from clean reset at least three consecutive times with:

- real cached inputs,
- scientifically consistent outputs,
- a valid evidence-driven branch,
- final disposition,
- result lock,
- ground truth inaccessible before unlock,
- reveal tied to the same locked run,
- frontend build passing,
- adequate runtime headroom.
