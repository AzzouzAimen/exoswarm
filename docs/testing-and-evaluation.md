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

For multi-agent parity, use `compare_scientific_outcomes`. It removes generated IDs, timestamps,
model prose, and model-call counts, while comparing terminal status/disposition, completed tests,
tool/action sequence, parameters, budgets, deterministic measurements with units/tolerances,
provenance, failures, lock state, and the zero-raw-sample invariant. A specialist rollout is
result-neutral only when this comparison passes against the two-role baseline.

Backend role tests must also cover the normal seven-call path, Observer/Signal concurrency,
role-context isolation, evidence citation validation, locked prompt hashes, explicit thinking
modes, reasoning-only/empty output rejection, optional-role safe skipping, and checkpoint recovery
without duplicate calls.

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
`scripts/run_live_backend_gate.py`; an adaptive path must reach all seven role phases through
FastAPI, expose SSE and sanitized accepted decisions, prove the promoted advisory handoff reaches
the Skeptic but not the Critic, expose safe artifact metadata, lock the result, and verify the
reveal against the exact locked hash. A decisive mandatory-evidence path requires only the final
Director and proves that the multi-agent layer does not defeat deterministic short-circuiting.

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
strict rejection. The structural fix was the bounded context projection (now `agent-context-v4`),
which omits unavailable and previously executed actions from model affordances while leaving the full registry in deterministic audit and
enforcement code. Before changing prompts or agent policy after an eval failure, inspect the exact
fixture proposal, model-visible action set, and deterministic expected outcome. Preserve the tests
that require relevant Critic proposals and omission of unavailable actions.

### Thinking-mode promotion record

The exact-model format preflight must pass before any role is marked confirmed. A low-cap
Director/Skeptic/Critic experiment reproduced `finish_reason=length`; the measured fix is a
thinking-only 20,000-token output allowance plus a 120-second deadline. Do not promote every role
merely because the toggle works. The retained profile is Director on with every branch-changing
role off. The five-state Skeptic-thinking candidate and its chat control both passed 10/10
first-attempt schema/semantic and decision-quality checks across four branches; because thinking
did not improve that action metric and increased latency, it remains an opt-in experiment. The
Director-only C11, P21, and B42 live gates passed without a disposition change, fallback, repair,
or provider error.

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
