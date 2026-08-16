# Technology

ExoSwarm uses one web application, one API service, one explicit investigation topology, and local
durable artifacts. The stack favors inspectable boundaries and reproducible execution over
distributed infrastructure.

## Application stack

| Layer | Implementation | Responsibility |
|---|---|---|
| Web | Next.js 16, React 19, TypeScript | Mission Control application and typed API projections |
| Styling and components | Tailwind CSS, Radix UI primitives | Responsive, accessible interface components |
| Scientific visualization | Plotly.js | Interactive light curves, periodograms, folds, and diagnostics |
| Central scene | React Three Fiber | One non-authoritative mission-control visualization |
| API | FastAPI, Pydantic v2, Uvicorn | REST control, typed schemas, health, and UI-safe projections |
| Event stream | Server-Sent Events | Ordered investigation updates with reconnect support |
| Investigation topology | LangGraph | Explicit node sequencing over a disposable routing envelope |
| Durable state | JSON and append-only JSONL | Atomic snapshots, evidence, decisions, traces, and recovery |
| Model integration | OpenAI Python client + Featherless.ai | Strict structured output for six bounded roles |
| Scientific computing | Lightkurve, Astropy, NumPy, SciPy, Pandas | Deterministic TESS processing and measurements |
| Reproducible plots | Matplotlib | Backend-generated scientific artifacts |
| Packaging and delivery | uv, pnpm, Docker, Caddy | Frozen installs, container builds, and HTTPS reverse proxy |
| Verification | pytest, Ruff, Vitest, ESLint, TypeScript, GitHub Actions | Contract, regression, build, and smoke checks |

## Authority mapping

| Concern | Authority |
|---|---|
| Route selection and stopping | Deterministic controller policy |
| Specialist interpretation | Bounded Featherless model roles |
| Action authorization | Pydantic schemas, registry, permissions, preconditions, and budgets |
| Measurements | Deterministic Python tools only |
| Mandatory diagnostics | Explicit controller logic |
| Hypothesis updates and final disposition | Deterministic rules over committed evidence |
| Scientific history | Append-only Evidence Ledger |
| Recovery | Atomic state plus prepared/completed invocation checkpoints |
| Catalog isolation | Separate viewer projection and backend-only audit gate |
| Tamper evidence | Canonical result bytes plus SHA-256 |

## Scientific implementation

| Task | Implementation |
|---|---|
| TESS FITS loading and quality flags | Lightkurve and Astropy FITS metadata |
| Normalization and detrending | Lightkurve, NumPy, and SciPy |
| Candidate search | `astropy.timeseries.BoxLeastSquares` |
| Period, epoch, depth, duration, and SNR | Astropy BLS plus deterministic NumPy calculations |
| Odd/even comparison | Per-transit deterministic Python analysis |
| Secondary-event search | Phase-window deterministic Python analysis |
| Harmonic test | Fixed P/2, P, and 2P trials |
| Contamination context | Cached neighbor data or explicitly labeled SPOC `CROWDSAP` fallback |
| Pixel/centroid localization | Registered as unavailable without cached target-pixel files |

The system deliberately does not introduce a database, distributed queue, vector store,
microservice split, or multiple model providers. Local JSON/JSONL persistence is an honest fit for
the fixed cached-target prototype and keeps every judged run inspectable.

Live inference reports model identity, calls, provider-supplied token usage, structured-output
validity, repairs, fallbacks, and latency from trace records. See [Featherless inference](inference.md).
