# Stargazer Index

## Contents

- [Snapshot and role](#snapshot-and-role)
- [Code map](#code-map)
- [Evaluation patterns worth adapting](#evaluation-patterns-worth-adapting)
- [Critical blinding difference](#critical-blinding-difference)
- [Suggested ExoSwarm eval translation](#suggested-exoswarm-eval-translation)
- [Do not adopt](#do-not-adopt)

## Snapshot and role

- Repository: <https://github.com/AIPS-UofT/Stargazer>
- Paper: <https://arxiv.org/abs/2604.15664>
- Indexed commit: `3f617667472061e253288c7b26f0e70f186f2dff`
- License: MIT for code; benchmark data is documented as CC BY 4.0.

Stargazer is a radial-velocity agent benchmark, not a TESS transit pipeline. Use it for reproducible task banks, hidden truth, deterministic evaluation, strict conjunctive criteria, baselines, traces, batch execution, and failure analysis. Do not reuse its numerical RV methods for transit photometry.

## Code map

| Concern | Pinned path / symbol | What to study | ExoSwarm caveat |
|---|---|---|---|
| Typed task contracts | [`stargazer/config.py`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/config.py) | Observation, system, planet, noise, and task structures | Create transit-specific scenario/evidence types |
| Deterministic synthetic tasks | [`stargazer/task_factory.py::TaskFactory`, `generate_task`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/task_factory.py) | Seeded generation and difficulty metadata | Keep generation truth inaccessible to the agent runtime |
| Durable task bank | [`stargazer/bank.py::TaskBank`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/bank.py) | Add/list/load boundaries for repeatable cases | Separate public inputs from private expected results on disk and in imports |
| Reset/step environment | [`stargazer/env.py::RvEnv`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/env.py) | Valid modes, observation construction, max steps, conjunctive success details | Its `step()` evaluates against truth immediately; ExoSwarm must defer this until lock |
| Deterministic grader | [`stargazer/evaluator.py::evaluate_submission`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/evaluator.py) | Likelihood/BIC, residuals, parameter matching, component metrics | ExoSwarm needs transit-specific criteria and pass/fail gates, not a reward as scientific confidence |
| Matching | [`stargazer/matching.py::planet_score_components`, `match_planets`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/matching.py) | Explicit per-parameter comparisons and assignment | Match only after result lock; encode aliases/harmonics deliberately |
| Action normalization | [`stargazer/agents/common.py::plan_to_action`, `validate_submission_semantics`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/agents/common.py) | Canonicalization and semantic validation after model output | Prefer ExoSwarm's schema validator and bounded action registry |
| Submit tool | [`stargazer/agents/tools/submit_action_tool.py`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/agents/tools/submit_action_tool.py) | Final submission schema and environment handoff | It returns truth-derived matching feedback; never do this pre-lock |
| Agent trace loop | [`stargazer/agents/tabular_agent.py::TabularRvAgent.run`, `_flush_trace`, `_trim_message_history`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/agents/tabular_agent.py) | Incremental traces, stop reasons, token counts, context trimming, tool-call records | Do not persist hidden reasoning; use structured decisions and concise reasons |
| Trace summaries | [`stargazer/agents/format_utils.py::convert_trace_to_json`, `_compute_statistics`, `_extract_analysis_timeline`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/agents/format_utils.py) | Deriving metrics and timelines from traces | Generate views from canonical events; HTML/Markdown are not state |
| Baselines | [`stargazer/benchmarks/baselines.py`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/benchmarks/baselines.py) | Null and simple deterministic baselines | Compare ExoSwarm agent policy to fixed investigation policies |
| Batch runner | [`run_agent_batch.py`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/run_agent_batch.py) | Repeated execution and artifact layout | Keep runs reproducible and model/config identifiers explicit |
| Watchdog | [`run_agent_batch_hard_timeout.py`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/run_agent_batch_hard_timeout.py) | Per-task process timeout, failure artifact, continue-on-timeout | Adapt terminal records; do not lose the partial trace on timeout |
| Tests | [`stargazer/tests/test_smoke.py`](https://github.com/AIPS-UofT/Stargazer/blob/3f617667472061e253288c7b26f0e70f186f2dff/stargazer/tests/test_smoke.py) | Contract, unit-conversion, evaluator, and environment smoke cases | Add positive and negative transit cases plus lock-invariant tests |

The repository contains both synthetic and archival-real task directories and separate classical/nested-sampling runners. Study their separation when designing ExoSwarm's scenario suite and deterministic baselines.

## Evaluation patterns worth adapting

- A task bank with stable IDs, seeded synthetic generation, cached real observations, and versioned metadata.
- Private truth stored outside the agent-visible observation and context assembler.
- Success requiring all critical criteria, not merely a high aggregate score.
- Metrics at three levels: final scientific result, trajectory behavior, and operational cost/latency.
- Baselines that answer whether the agent adds value over a fixed or deterministic policy.
- Hard step/tool/token/time limits with explicit terminal reasons.
- Trace exports that support failure clustering and regression comparison.
- Skills derived from recurring trace failures, then tested on a held-out set rather than the cases used to write the skill.

## Critical blinding difference

Stargazer can evaluate a submission during `RvEnv.step()` and return match-derived metrics, success details, and hints. Even after removing an obvious truth field, this feedback leaks distance from the hidden answer and permits iterative guessing.

ExoSwarm must split this into two processes:

```text
investigation runtime -> evidence-only feedback -> lock result
                                              |
                                              v
private evaluation runner -> truth comparison -> eval artifact
```

The private evaluator must not be imported by agent modules, reachable through an agent tool, serialized into context, or called before the result-lock artifact is durably written.

## Suggested ExoSwarm eval translation

| Stargazer pattern | ExoSwarm version |
|---|---|
| Synthetic RV system | Injected transit, eclipsing-binary-like signal, harmonic/alias case, flat/noise-only curve |
| Real archival RV tasks | Cached real TESS observations with opaque runtime IDs |
| Parameter matching | Period/epoch/depth/duration tolerances with explicit harmonic policy |
| Residual/BIC criteria | Science-tool-specific deterministic ranges and diagnostic completion |
| Exact planet count | Correct candidate/disposition count where the scenario defines it |
| Agent steps | Valid action choice, mandatory diagnostic coverage, no repeated action, bounded termination |
| Reward | Separate pass criteria and diagnostic metrics; never display it as scientific probability |
| Batch trace | Versioned scenario ID, model/config, actions, evidence references, costs, latency, terminal reason |

Keep a development set for prompt/harness iteration and a locked holdout set for regression claims. A successful demo target alone is not an evaluation suite.

## Do not adopt

- PythonREPL or arbitrary code execution as the normal agent tool.
- Mid-investigation truth matching, success hints, repeated scored submissions, or “best submission” selection.
- A scalar reward as the scientific disposition, validation probability, or user-facing confidence.
- RV-specific dynamics, coordinate conversions, priors, or parameter tolerances for transit work.
- Full model conversations or hidden chain-of-thought in durable traces.
- Benchmark fixtures without checking their license, attribution, and suitability for ExoSwarm's blind target policy.
