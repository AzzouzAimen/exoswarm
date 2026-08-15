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

The real Featherless canary is a separate, opt-in command and never participates in offline tests:

```console
$env:FEATHERLESS_API_KEY = "..."
uv run --project apps/api --extra agents python scripts/run_featherless_canary.py --repeats 10 --output evals/featherless_canary.json
```

Each repeat checks both the Skeptic and Critic schemas (20 primary decisions at the default), makes
at most one repair after an invalid response, and reports measured validity, repairs, usage, and
latency. Without `FEATHERLESS_API_KEY` it exits successfully with an explicit `SKIPPED` report.

After that canary passes, `scripts/run_live_backend_gate.py` runs TARGET-P21 with live Featherless
through FastAPI and SSE, then verifies artifacts, lock, and reveal. Its sanitized summary is written
to `evals/live_backend_gate.json`.
