# 48-Hour Scope and Build Order

## P0 - Cannot ship without

- reliable cached TESS -> BLS -> folded-transit pipeline,
- one planet-like case,
- one false-positive/eclipsing-binary case,
- different evidence-driven agent paths,
- opaque target identity,
- mechanically enforced result lock,
- no fake confidence,
- precise scientific claim language,
- Evidence Ledger,
- bounded adaptive experiment selection,
- cached demonstration data,
- reproducible traces,
- blind-protocol test.

## P1 - Major competitive advantage

- real pixel/centroid contamination test,
- visible hypothesis updates,
- Critic review,
- agent-vs-fixed-policy mini evaluation,
- repeated-run consistency metric,
- value-of-information logging,
- numeric-provenance guardrail.

## P2 - Only after everything works

- improved transit fitting/uncertainties beyond the required basic level,
- multi-model routing,
- broader target coverage,
- additional diagnostics,
- additional agents,
- more sophisticated probabilistic validation,
- multi-sector stitching.

## Build order

### Phase 0 - Scaffold

- monorepo structure,
- Python/JS package management,
- schemas/enums/events,
- dependency boundaries,
- result-lock/catalog-gate skeleton,
- FastAPI health + API/SSE skeleton,
- Next.js mission-control shell,
- CI and boundary tests.

No real scientific or model integrations yet.

### Phase 1 - Deterministic scientific core

- cached input loader + provenance,
- quality/preprocessing,
- BLS + phase fold,
- period/epoch/depth/duration/SNR,
- mandatory odd/even + secondary + contamination baseline,
- harmonic test,
- artifact plots,
- science validation fixtures.

### Phase 2 - Investigation runtime

- `InvestigationState`,
- tool registry/permissions,
- mandatory controller,
- Evidence Ledger + state updates,
- bounded loop/stopping rules,
- Featherless model client,
- Director/Skeptic structured decisions,
- Critic review,
- agent failure/fallback handling.

### Phase 3 - Blind lock/reveal

- backend-only target mapping,
- pre-lock agent context filters,
- canonical result serialization + SHA-256,
- locked artifact,
- gated NASA reveal,
- CI proof of blindness.

### Phase 4 - Full frontend integration

- real Plotly scientific data,
- SSE-driven timeline/state,
- evidence board,
- adaptive-decision panel,
- Critic verdict,
- lock/reveal experience,
- one central R3F scene.

### Phase 5 - Evals + reproducibility

- 6-10 curated cases over time,
- branch-diversity tests,
- fixed-policy baseline,
- pass^3 consistency,
- `make reproduce`,
- repository artifact/report output.

### Phase 6 - Demo hardening

Only after the core path works:

- deterministic reset,
- no-network/cached operation,
- model timeout handling,
- frontend refresh/reconnect,
- three consecutive clean runs,
- final video route.

## Four-person parallel ownership

Suggested split from the supplied plan:

| Member | Main responsibility | Stack |
|---|---|---|
| 1 - Science | TESS pipeline and deterministic astronomy | Lightkurve, Astropy, NumPy, SciPy, Matplotlib |
| 2 - Agents | LangGraph harness and Featherless agents | LangGraph, Pydantic, OpenAI SDK, Featherless |
| 3 - Frontend | mission-control interface/visualization | Next.js, TypeScript, Tailwind, shadcn/ui, Heroicons, Plotly, R3F |
| 4 - Integration | API, events, locking, evals, deployment | FastAPI, SSE, JSONL, pytest, Docker, Railway, GitHub Actions |

Coordinate through typed contracts, not ad hoc shared state.
