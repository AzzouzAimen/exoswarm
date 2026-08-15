# ExoSwarm

**AI Mission Control for Agent-Orchestrated Exoplanet Investigation**

ExoSwarm is an AI-orchestrated TESS investigation system that uses deterministic astronomy tools to test and falsify competing explanations for transit-like signals, adaptively chooses which scientific evidence to seek next, and locks its measurements before comparing them with NASA ground truth.

ExoSwarm is **not** an LLM planet detector. Numerical measurements belong to deterministic scientific code. The agent layer decides what evidence to seek next, which competing hypothesis deserves attention, and when the implemented evidence is sufficient to stop.

## Core architecture

The project deliberately combines a deterministic workflow with bounded agentic control:

- **Deterministic scientific layer:** TESS loading, preprocessing, BLS, phase folding, measurements, odd/even checks, secondary-eclipse checks, harmonic tests, pixel/centroid diagnostics, hypothesis-update rules, result locking, and catalog gating.
- **Agent layer:** bounded decisions over structured evidence using a Scientific Director with Observer, Signal, Transit Hunter, Skeptic, and Critic roles.
- **Mandatory baseline:** safety-critical vetting is code-enforced and cannot be skipped by the model.
- **Adaptive layer:** the Skeptic selects a discriminating follow-up experiment from a bounded registry; the Critic returns APPROVE, REVISE, or VETO.
- **Blind protocol:** agents see opaque target IDs; recognizable identity and NASA ground truth are unavailable until the result is locked.
- **Evidence Ledger:** append-only structured scientific evidence powers agent context, auditability, UI storytelling, evaluation, and reproducibility.

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

The P0 scientific path is:

```text
cached TESS data
  -> quality/preprocessing
  -> BLS search
  -> phase folding
  -> period/depth/duration/SNR
  -> odd/even test
  -> secondary-eclipse test
  -> P/2-P-2P harmonic test
  -> one real pixel/centroid spatial diagnostic
```

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

A valid demo must show at least one planet-like case and one false-positive/eclipsing-binary case taking visibly different evidence-driven trajectories.

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
      reveal.json             # only after lock + reveal
      artifacts/
        raw_lightcurve.png
        bls_periodogram.png
        folded_lightcurve.png
        centroid.png
```

`make reproduce` should eventually be able to rerun the deterministic path from cached real source data without requiring astronomy-data network access and verify the locked artifacts.

## Project status and scope

The first coding-agent task is **repository scaffold only**. Do not silently expand the initial scaffold into a full astronomy pipeline or a polished demo. See:

- [`FIRST_AGENT_PROMPT.md`](FIRST_AGENT_PROMPT.md) - first prompt for the coding agent.
- [`AGENTS.md`](AGENTS.md) - repository-wide coding-agent rules.
- [`docs/00_SOURCE_OF_TRUTH.md`](docs/00_SOURCE_OF_TRUTH.md) - source-derived constraints vs scaffold conventions.
- [`docs/11_48H_SCOPE_AND_BUILD_ORDER.md`](docs/11_48H_SCOPE_AND_BUILD_ORDER.md) - P0/P1/P2 priority and implementation order.

## Scientific claim language

Preferred wording:

> The planetary interpretation survives the implemented vetting.

Avoid claims that ExoSwarm autonomously confirms or discovers planets. If NASA later reveals a confirmed-planet status, that status belongs to the external catalog, not to ExoSwarm's photometric vetting.
