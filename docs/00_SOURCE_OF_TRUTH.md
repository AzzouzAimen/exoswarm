# Source of Truth and Derived Scaffold Decisions

This context pack was distilled from the supplied ExoSwarm full-concept PDF, the supplied 48-hour tech-stack PDF, and the provided coding-agent skill files. The coding agent will not receive the PDFs, so this repository documentation is the operational source of truth.

## Final-stretch priority override

The original concept remains the source for scientific and architectural invariants. For the
remaining hackathon implementation, `docs/15_FINAL_STRETCH_PRIORITIES.md` overrides older priority,
build-order, and breadth recommendations. In particular:

- ship a legible end-to-end software system before expanding scientific coverage,
- keep the Scientific Director as deterministic orchestration code, not a distinct LLM call,
- make the Featherless inference path, structured-output handling, and measured run statistics
  visible,
- keep only three representative end-to-end evaluation cases: planet-like, eclipsing-binary-like,
  and inconclusive,
- do not build the fixed-policy ablation or `pass^3` metric,
- do not add new transit fitting or broad uncertainty propagation,
- preserve pixel/centroid work as a high-value P1 differentiator behind a short go/no-go acceptance
  check rather than making it a P0 blocker,
- prioritize clean setup, cached reproducibility, blind-lock proof, failure handling, documentation,
  and the judged demo path.

This changes delivery priority, not scientific truth. Deterministic measurements, typed evidence,
agent-safe context, provenance, result locking, catalog gating, and precise claim language remain
non-negotiable.

## Source-derived requirements

The following are requirements carried directly from the supplied planning context:

- ExoSwarm is an AI-orchestrated scientific investigation layer, not an LLM numerical detector.
- Deterministic astronomy code is the numerical authority.
- Agentic behavior must affect the scientific trajectory through evidence-dependent experiment selection.
- Mandatory diagnostics are structural/code-enforced; adaptive experiments happen after the baseline.
- The architecture is manager + bounded specialists, not unrestricted multi-agent conversation.
- Core roles: Scientific Director, Observer Agent, Signal Agent, Transit Hunter, Skeptic Agent, Critic Agent.
- The Skeptic chooses a bounded discriminating experiment; the Critic returns APPROVE / REVISE / VETO.
- Investigation state is typed/structured; conversation text is not the source of truth.
- Agent context is compact; raw light curves, FITS/TPF arrays, and hidden catalog truth do not enter model context.
- Scientific actions are validated and bounded; maximum turns/experiment budgets are enforced by code.
- Evidence is append-only and recorded in an Evidence Ledger.
- Ground-truth identity/catalog access is gated until after result lock.
- The result is serialized and SHA-256 hashed before reveal.
- The demo should include one planet-like case and one false-positive/eclipsing-binary case with visibly different trajectories.
- Core scientific path: cached TESS data, detrending, BLS, phase folding, period/depth/duration, odd/even, secondary eclipse, P/2-P-2P harmonic test, and one real spatial pixel/centroid diagnostic.
- Scientific claims must remain candidate/vetting claims, not autonomous confirmation claims.
- Frontend: Next.js + TypeScript + Tailwind + shadcn/ui + Heroicons; Plotly for scientific charts; React Three Fiber only for one central mission-control scene.
- Backend: FastAPI + Uvicorn + SSE + LangGraph + Pydantic v2 + OpenAI Python SDK, with Featherless AI and DeepSeek-V4-Flash-0731 as the core model plan.
- Science: Lightkurve, Astropy, NumPy, SciPy, Pandas, Matplotlib, httpx.
- Tooling: Python 3.12, uv, pnpm, pytest/pytest-asyncio, Ruff, TypeScript/ESLint, GitHub Actions, Docker, Vercel, Railway.
- Core persistence uses local files, JSON/JSONL, cached FITS inputs, and run artifacts; no database is required for the core build.
- `make reproduce` is a desired reproducibility command using cached real inputs.

## Scaffold conventions introduced by this pack

The source material does not specify every filename, endpoint, enum, or module name. This pack introduces the following **derived conventions** to make the first coding task unambiguous:

- monorepo-style `apps/web` + `apps/api` layout,
- Python package name `exoswarm`,
- module names under `domain/`, `science/`, `agents/`, `investigation/`, `security/`, `services/`, and `api/`,
- REST endpoint paths in `docs/08_API_EVENTS.md`,
- SSE event names in `docs/08_API_EVENTS.md`,
- a `state.json` snapshot in addition to source-required JSONL/result artifacts,
- a run directory nested by opaque target ID and run ID to support repeated eval runs,
- root `Makefile` commands for dev/test/lint/build/reproduce,
- environment variable names documented in the scaffold guide.

These conventions are intentionally small and reversible. They should not be treated as scientific facts or as requirements from the original PDF when discussing the project externally.

## When a gap appears

Do not silently invent scientific behavior. Prefer this order:

1. preserve a typed interface,
2. return an explicit not-implemented/error state,
3. add a TODO that names the missing contract,
4. ask for a decision only when implementation cannot remain safely reversible.
