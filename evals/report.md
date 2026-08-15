# ExoSwarm harness evaluation

Suite: `exoswarm-harness-adversarial-v1`

Result: **PASS** — 24/24 scenarios passed.

| Scenario | Result | Terminal status | Adaptive tools |
|---|---:|---|---|
| `clean_planet_like` | PASS | READY_TO_LOCK | — |
| `eclipsing_binary_adverse` | PASS | READY_TO_LOCK | harmonic_test |
| `ambiguous_inconclusive` | PASS | INSUFFICIENT_EVIDENCE | alternate_detrend |
| `evidence_branch_contamination` | PASS | READY_TO_LOCK | centroid_localization |
| `irrelevant_valid_action` | PASS | READY_TO_LOCK | — |
| `malformed_primary_valid_repair` | PASS | READY_TO_LOCK | harmonic_test |
| `malformed_primary_repair_failure` | PASS | FAILED | — |
| `provider_timeout_explicit_fallback` | PASS | READY_TO_LOCK | harmonic_test |
| `stale_context_mismatched_decision` | PASS | FAILED | — |
| `unaffordable_action` | PASS | READY_TO_LOCK | — |
| `repeated_action` | PASS | FAILED | — |
| `tool_failure` | PASS | FAILED | harmonic_test |
| `tool_timeout` | PASS | FAILED | harmonic_test |
| `restart_prepared_action` | PASS | READY_TO_LOCK | harmonic_test |
| `context_pressure_trimming` | PASS | INSUFFICIENT_EVIDENCE | harmonic_test |
| `runner_no_progress` | PASS | FAILED | — |
| `budget_step_exit` | PASS | BUDGET_EXHAUSTED | — |
| `budget_model_exit` | PASS | BUDGET_EXHAUSTED | — |
| `budget_tool_exit` | PASS | BUDGET_EXHAUSTED | — |
| `budget_adaptive_exit` | PASS | READY_TO_LOCK | — |
| `budget_cost_exit` | PASS | READY_TO_LOCK | — |
| `budget_critic_revision_exit` | PASS | BUDGET_EXHAUSTED | — |
| `budget_runner_advance_exit` | PASS | FAILED | — |
| `budget_runner_wall_clock_exit` | PASS | FAILED | — |

## Coverage notes

- Deterministic branch count: 4.
- Durable state/trace/evidence artifact reload checks: 24.
- Repeated / outside-trajectory tool calls: 0 / 0.
- Raw provider bodies, prompts, recognizable identity, local source paths, ground truth, and raw arrays are scanned out of persisted artifacts.
