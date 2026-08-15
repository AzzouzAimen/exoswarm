# Locked harness evaluations

The versioned deterministic harness suite lives under `harness/v1/`. Scenario definitions and
acceptance assertions are separate JSON files and their SHA-256 digests are pinned in `lock.json`.
The evaluator runs the real controller, context assembly, scripted model-client boundary, tool
registry, filesystem persistence, and runner. Every run's state snapshot, trace, and evidence
ledger are independently reloaded and checked for ordering, consistency, privacy, and budget
invariants. This is artifact reload verification, not event-sourced state reconstruction.

Run it from the repository root:

```console
uv run --project apps/api python scripts/run_harness_evals.py
```

This writes `evals/report.json` and `evals/report.md`. Add `--keep-runs <directory>` only when
investigating a failure.

The separately locked cached-real TESS suite covers five official SPOC light curves: a clean
planet-like case, two hot-Jupiter evidence profiles, a cataloged eclipsing binary recovered at its
half-period, and an intentionally inconclusive shallow signal. It runs the complete backend,
locks every lockable result, reveals truth only afterward, and verifies period/harmonic,
disposition, mandatory-test, hash, and zero-raw-sample assertions:

```console
uv run --project apps/api --extra science --extra agents python scripts/run_cached_real_tess_evals.py
```

The versioned criteria are in `real_tess/v1/cases.json`; their digest is pinned in
`real_tess/v1/lock.json`. The generated report is `cached_real_tess_report.json`.

The real Featherless canary is a separate, opt-in command and never participates in offline tests:

```console
$env:FEATHERLESS_API_KEY = "..."
uv run --project apps/api --extra agents python scripts/run_featherless_canary.py --repeats 10 --output evals/featherless_canary.json
```

Each repeat checks both the Skeptic and Critic schemas (20 primary decisions at the default), makes
at most one repair after an invalid response, and reports measured validity, repairs, usage, and
latency. Without `FEATHERLESS_API_KEY` it exits successfully with an explicit `SKIPPED` report.
The active demo profile keeps branch-changing roles in chat mode and enables
exact-model-preflight-confirmed thinking for the Director. The canary does not exercise Director,
so `featherless_canary_off_v6.json` is the branch-policy control;
`featherless_canary_thinking_mixed.json` is the passing but unpromoted Skeptic-thinking candidate.
The rejected both-action-roles-thinking experiment and the low-cap reproduction remain separate
reports so failures are not overwritten.

After that canary passes, `scripts/run_live_backend_gate.py --target <opaque-id>` runs one cached
target with live Featherless through FastAPI and SSE, then verifies artifacts, lock, and reveal.
Adaptive branches require all seven role phases; a decisive mandatory-evidence branch requires the
final Director only, preserving deterministic short-circuit behavior.
The final-profile summaries are `live_backend_gate_C11_director_thinking.json`,
`live_backend_gate_C11_director_thinking_repeat_2.json`,
`live_backend_gate_C11_director_thinking_repeat_3.json`,
`live_backend_gate_P21_director_thinking.json`, and
`live_backend_gate_B42_director_thinking.json`. Broader Director/Skeptic experiment reports and
historical chat-mode reports remain available for comparison rather than being relabeled as the
promoted configuration.
