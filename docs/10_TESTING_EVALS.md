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

## Agent evaluation suite

Create roughly 6-10 curated cases over time, including:

- several clean planet-like/confirmed-planet holdouts,
- one or more eclipsing binaries,
- one contaminated candidate,
- one noisy/variable target,
- one deliberately difficult/inconclusive case.

Do not optimize the agent for one demo star.

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
- contamination-like evidence,
- weak/noisy evidence.

Assert that at least some cases select different valid next actions. If every path is predetermined, the behavior belongs in a workflow, not the agent.

## Fixed-policy ablation

Baseline:

```text
BLS -> odd/even -> secondary -> centroid -> final
```

Compare against adaptive selection on the same cases:

- correct next experiment where definable,
- correct final disposition,
- unnecessary experiments,
- repeated tool calls,
- invalid requests,
- mandatory-test completion,
- mean experiments,
- realized information value,
- turns,
- latency,
- cost,
- consistency.

If adaptive and fixed systems perform similarly, report that rather than manufacturing a benefit.

## Consistency

For important stochastic cases, run multiple times and track `pass^3`: whether the case succeeds correctly across three independent runs.

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
