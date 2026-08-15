# ExoSwarm

**AI Mission Control for Agent-Orchestrated Exoplanet Investigation**

ExoSwarm is an AI-orchestrated TESS investigation system that uses deterministic astronomy tools to test and falsify competing explanations for transit-like signals, adaptively chooses which scientific evidence to seek next, and locks its measurements before comparing them with NASA ground truth.

ExoSwarm is **not** an LLM planet detector. Numerical measurements belong to deterministic scientific code. The agent layer decides what evidence to seek next, which competing hypothesis deserves attention, and when the implemented evidence is sufficient to stop.

## Who it is for

ExoSwarm is a reference implementation for engineers building auditable AI decision systems in
science, finance, security, and other evidence-heavy domains. The reusable pattern is an LLM that
chooses which bounded, potentially expensive deterministic analysis to run next while a typed
ledger records what happened. Its blind-lock protocol also addresses benchmark contamination: a
result on public data is more credible when the system can prove the decision layer could not see
the answer before committing its result.

## Core architecture

The project deliberately combines a deterministic workflow with bounded agentic control:

- **Deterministic scientific layer:** TESS loading, preprocessing, BLS, phase folding, measurements, odd/even checks, secondary-eclipse checks, harmonic tests, contamination diagnostics, hypothesis-update rules, result locking, and catalog gating.
- **Control layer:** deterministic orchestration owns phases, budgets, permissions, retries, and stopping. Featherless-backed Skeptic and Critic calls provide bounded judgment where experiment selection benefits from it; role labels do not require separate LLM calls.
- **Mandatory baseline:** safety-critical vetting is code-enforced and cannot be skipped by the model.
- **Adaptive layer:** the Skeptic selects a discriminating follow-up experiment from a bounded registry; the Critic returns APPROVE, REVISE, or VETO.
- **Blind protocol:** agents see opaque target IDs; recognizable identity and NASA ground truth are unavailable until the result is locked.
- **Evidence Ledger:** append-only structured scientific evidence powers agent context, auditability, UI storytelling, evaluation, and reproducibility.

## Inference layer

Featherless.ai is the intended live inference provider, with `DeepSeek-V4-Flash-0731` as the single
primary model. The current harness uses a scripted inference client and deliberately leaves the live
provider unconfigured. Before submission, the live path must expose measured call count, input/output
tokens, schema-valid rate, repair rate, fallback rate, latency, and model identity for each run. Raw
light-curve samples sent to the model must remain **zero**; models receive compact evidence packets
with deterministic measurements and provenance references.

See [`docs/inference.md`](docs/inference.md) for the implementation and reporting contract. Never
replace unavailable metrics with estimates in the README, UI, demo, or artifacts.

## 48-hour stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript |
| Styling | Tailwind CSS + shadcn/ui |
| Icons | Heroicons |
| Scientific charts | Plotly.js + react-plotly.js |
| Central 3D scene | React Three Fiber, one mission-control scene only |
| Backend | FastAPI + Uvicorn |
| Realtime | Server-Sent Events (SSE) |
| Agent orchestration | LangGraph |
| Schemas | Pydantic v2 |
| LLM client/provider | OpenAI Python SDK -> Featherless AI |
| Primary model | DeepSeek-V4-Flash-0731 |
| TESS/science | Lightkurve, Astropy, NumPy, SciPy, Pandas |
| Reproducible plots | Matplotlib |
| HTTP | httpx |
| Python tooling | Python 3.12, uv, pytest, pytest-asyncio, Ruff |
| JS tooling | pnpm, ESLint, TypeScript |
| CI/deploy | GitHub Actions, Vercel, Railway, Docker |

**Visualization rule:** use React Three Fiber only for the single central mission-control visualization. All scientific charts and diagnostics stay in Plotly.

## Repository layout

The intended scaffold is documented in [`docs/03_REPO_SCAFFOLD.md`](docs/03_REPO_SCAFFOLD.md). At a high level:

```text
apps/web/                    Next.js mission-control frontend
apps/api/                    FastAPI + ExoSwarm Python package
data/                        cached scientific inputs and target manifests
runs/                        reproducible run artifacts
evals/                       curated evaluation cases and reports
scripts/                     reproducibility and utility entrypoints
docs/                        architecture and implementation contracts
.agents/skills/              coding-agent skill files
```

## Scientific path

The shippable P0 scientific path is:

```text
cached TESS data
  -> quality/preprocessing
  -> BLS search
  -> phase folding
  -> period/depth/duration/SNR
  -> odd/even test
  -> secondary-eclipse test
  -> P/2-P-2P harmonic test
  -> basic contamination context
```

A real pixel/centroid diagnostic remains a high-value P1 differentiator. Attempt it after the
end-to-end core is stable and keep it when a real cached TPF case passes a short acceptance check.
If it misses that checkpoint, ship an honestly labeled alternate-aperture test plus cached
neighbor/contamination context and do not imply pixel-level localization.

All measurements must have explicit units, method/provenance, and explicit failure states. Where uncertainty is not available, report a declared tolerance rather than fake precision.

## Investigation path

```text
observe
  -> prepare signal
  -> detect candidate
  -> establish competing hypotheses
  -> complete mandatory baseline vetting
  -> Skeptic selects adaptive experiment
  -> Critic reviews
  -> deterministic tool executes
  -> Evidence Ledger appends result
  -> deterministic hypothesis update
  -> continue or stop
  -> lock result + SHA-256
  -> unlock NASA reveal
```

A valid demo must show one planet-like case and one false-positive/eclipsing-binary case taking
visibly different evidence-driven trajectories. A third inconclusive case belongs in the compact
evaluation suite but need not consume the primary three-minute demo.

## Blindness and result lock

Before `RESULT_LOCKED`, agent-visible code paths must not expose:

- recognizable target identity when avoidable,
- known planetary parameters,
- NASA confirmation status,
- ground-truth catalog values,
- a ground-truth lookup tool.

The final result is serialized and hashed before any reveal. The catalog is an evaluator, not an input to the investigation.

## Artifacts

Conceptual run output:

```text
runs/
  TARGET-X17/
    <run-id>/
      state.json
      trace.jsonl
      result.json
      result.json.sha256
      inference_summary.json
      reveal.json             # only after lock + reveal
      artifacts/
        raw_lightcurve.png
        bls_periodogram.png
        folded_lightcurve.png
        centroid.png
```

`make reproduce` must become the submission-grade cached/no-network reproduction path and verify the
result artifact hash. The current command reproduces the deterministic candidate-search slice; it
does not yet reproduce the complete locked investigation.

## Project status and scope

The deterministic vertical slice can filter, detrend, search, phase-fold, and measure a local cached
TESS light-curve FITS product with provenance and Evidence Ledger output. The bounded investigation
harness is operational with scripted inference, durable state/trace/ledger recovery, validated tool
requests, and result-lock/catalog-gate boundaries. The default API still lacks its backend target
source mapping, and the live Featherless adapter, remaining diagnostics, full two-target path,
run-level inference summary, and real reveal provider remain unfinished.

## Scaffold quick start

Requirements: Python 3.12 with `uv`, Node.js 24, and `pnpm` 11.

```bash
uv sync --project apps/api --extra science
pnpm install --frozen-lockfile
make test
make lint
make build
```

For local development, run `make dev-api` and `make dev-web` in separate terminals. With the ignored
cached-real FITS present, `make reproduce` reruns the deterministic local candidate analysis and
never contacts an astronomy-data service or generates placeholder science.

Do not invent capabilities or fake demo values while completing the ranked final-stretch work. See:

- [`AGENTS.md`](AGENTS.md) - repository-wide coding-agent rules.
- [`docs/00_SOURCE_OF_TRUTH.md`](docs/00_SOURCE_OF_TRUTH.md) - source-derived constraints vs scaffold conventions.
- [`docs/11_48H_SCOPE_AND_BUILD_ORDER.md`](docs/11_48H_SCOPE_AND_BUILD_ORDER.md) - P0/P1/deferred priority and implementation order.
- [`docs/13_HARNESS_SCAFFOLD.md`](docs/13_HARNESS_SCAFFOLD.md) - implemented harness boundary and authority classes.
- [`docs/15_FINAL_STRETCH_PRIORITIES.md`](docs/15_FINAL_STRETCH_PRIORITIES.md) - current cut list, sequencing, and submission gates.
- [`docs/inference.md`](docs/inference.md) - Featherless integration and measured inference-statistics contract.

## Scientific claim language

Preferred wording:

> The planetary interpretation survives the implemented vetting.

Avoid claims that ExoSwarm autonomously confirms or discovers planets. If NASA later reveals a confirmed-planet status, that status belongs to the external catalog, not to ExoSwarm's photometric vetting.
