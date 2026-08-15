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
- blind-protocol test,
- live Featherless Skeptic/Critic path with schema validation, bounded repair, and fallback,
- measured inference summary visible in artifacts/UI,
- `make reproduce` for the complete locked cached path,
- clear README setup, architecture, limitations, and target-user framing.

## P1 - Major competitive advantage

- real pixel/centroid contamination test with a cached-real acceptance case,
- visible hypothesis updates,
- Critic review,
- cost-weighted adaptive budget visible in decisions and UI,
- evidence-dependent Observer/Signal role only if it creates a visibly different valid branch,
- polished mission-control storytelling around real state, failures, inference, and lock/reveal,
- numeric-provenance guardrail.

## Deferred beyond the hackathon submission

- improved transit fitting/uncertainties beyond the required basic level,
- multi-model routing,
- broader target coverage,
- additional diagnostics,
- additional agents,
- more sophisticated probabilistic validation,
- multi-sector stitching.

These are not an active final-stretch backlog. Revisit them after submission rather than consuming
time that can improve the scored P0/P1 system.

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

### Phase 1 - Stabilize the deterministic vertical slice

- cached input loader + provenance,
- quality/preprocessing,
- BLS + phase fold,
- period/epoch/depth/duration/SNR,
- mandatory odd/even + secondary + basic contamination baseline,
- harmonic/alternate-aperture diagnostics only as required by the selected cases,
- artifact plots,
- science validation fixtures.

After this vertical path is stable, give centroid localization a focused implementation and
cached-real acceptance window because it is both scientifically useful and visually distinctive.
If it misses the checkpoint, defer it and use an honestly labeled fallback. Do not implement new
transit fitting or broad uncertainty propagation first.

### Phase 2 - Investigation runtime

- `InvestigationState`,
- tool registry/permissions,
- mandatory controller,
- Evidence Ledger + state updates,
- bounded loop/stopping rules,
- live Featherless model client for Skeptic/Critic,
- deterministic Director/controller policy plus Skeptic structured decisions,
- Critic review,
- structured-output attempt -> validate -> bounded repair -> deterministic fallback,
- inference usage/latency/validation tracing,
- cost-weighted adaptive budget.

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

### Phase 5 - Three cases + reproducibility

- planet-like, eclipsing-binary-like, and inconclusive cases,
- branch-diversity tests,
- complete cached `make reproduce` with locked hash verification,
- repository artifact/report output.

### Phase 6 - Demo hardening

Only after the core path works:

- deterministic reset,
- no-network/cached operation,
- model timeout handling,
- frontend refresh/reconnect,
- three consecutive clean runs,
- final video route.

Then freeze low-value feature scope. With submission gates green, continue only with the ranked P1
differentiators above—especially accepted centroid evidence and mission-control storytelling—or
with work that fixes a demonstrated blocker in setup, the judged flow, blinding, inference,
reproducibility, or truthful presentation.

### Phase 7 - Documentation and submission assets

- clean-clone quickstart that is actually exercised,
- architecture and bounded-inference explanation,
- Featherless statistics from recorded traces,
- error-handling and blind-lock proof,
- reproduction instructions and limitations,
- concise three-minute video route with captions,
- public repository/video/link checks.

Documentation and the video are deliverables, not cleanup work after all optional code is finished.

## Four-person parallel ownership

Suggested split from the supplied plan:

| Member | Main responsibility | Stack |
|---|---|---|
| 1 - Science | TESS pipeline and deterministic astronomy | Lightkurve, Astropy, NumPy, SciPy, Matplotlib |
| 2 - Agents | LangGraph harness and Featherless agents | LangGraph, Pydantic, OpenAI SDK, Featherless |
| 3 - Frontend | mission-control interface/visualization | Next.js, TypeScript, Tailwind, shadcn/ui, Heroicons, Plotly, R3F |
| 4 - Integration | API, events, locking, evals, deployment | FastAPI, SSE, JSONL, pytest, Docker, Railway, GitHub Actions |

Coordinate through typed contracts, not ad hoc shared state.
