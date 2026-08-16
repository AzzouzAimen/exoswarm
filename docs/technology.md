# 48-Hour Tech Stack

## Core application stack

| Layer | Technology | Purpose | Priority |
|---|---|---|---|
| Frontend framework | Next.js + TypeScript | Mission-control web interface | Core |
| Styling | Tailwind CSS | Fast responsive styling | Core |
| UI components | shadcn/ui | Panels, cards, tabs, dialogs, controls | Core |
| Icons | Heroicons | Interface icons | Core |
| Scientific visualization | Plotly.js + react-plotly.js | Light curves, periodograms, folded signals, diagnostics | Core |
| 3D mission-control visualization | React Three Fiber | Single central scene only | Core |
| Backend API | FastAPI | Frontend/agent/science API | Core |
| Backend server | Uvicorn | Run FastAPI | Core |
| Realtime | Server-Sent Events | Stream investigation events to UI | Core |
| Agent orchestration | LangGraph | State machine / bounded workflow | Core |
| Schemas | Pydantic v2 | Decisions, evidence, candidates, API models | Core |
| LLM client | OpenAI Python SDK | OpenAI-compatible Featherless client | Core |
| LLM provider | Featherless AI | Agent inference | Core |
| Primary model | DeepSeek-V4-Flash-0731 | Bounded scientific decisions | Core |
| Scientific data | Lightkurve | TESS light curves and Target Pixel Files | Core |
| Astronomy | Astropy | BLS and time-series utilities | Core |
| Numerical | NumPy + SciPy | Measurements/statistics/signal processing | Core |
| Dataframes | Pandas | Evaluation/tabular data | Useful |
| Reproducible artifacts | Matplotlib | Saved plots | Core |
| HTTP | httpx | External requests when required | Core |

## Agent/scientific architecture mapping

| Component | Implementation |
|---|---|
| Scientific Director | product label for deterministic controller/routing logic; not a P0 model call |
| Observer Agent | P1 after the core path, only for a real bounded data-quality decision |
| Signal Agent | P1 after the core path, only for a real evidence-dependent preprocessing choice |
| Transit Hunter | deterministic controller + scientific tools for P0 |
| Skeptic Agent | Featherless structured decision |
| Critic Agent | structured APPROVE / REVISE / VETO |
| Durable shared state | Pydantic `InvestigationState` + JSON/JSONL artifacts |
| Graph routing envelope | LangGraph `StateGraph` + minimal `run_id`/route `TypedDict` |
| Validation | Pydantic + deterministic policy checks |
| Maximum turns | LangGraph / Python |
| Experiment budget | cost units in state + per-action cost + Python checks |
| Mandatory diagnostics | explicit Python control logic |
| Hypothesis updates | deterministic Python rules |
| Measurements | deterministic Python only |
| Evidence Ledger | append-only Python / JSONL |
| Catalog gating | explicit Python module |
| Result lock | canonical serialization + SHA-256 |
| Reveal | separate gated NASA lookup layer |

## Scientific computation mapping

| Task | Technology |
|---|---|
| TESS FITS / TPF loading | Lightkurve |
| Quality flags | Lightkurve |
| Normalization | Lightkurve / NumPy |
| Detrending | Lightkurve / SciPy |
| BLS | `astropy.timeseries.BoxLeastSquares` |
| Phase folding | Lightkurve / NumPy |
| Period measurement | Astropy BLS |
| Transit depth/duration | NumPy / SciPy |
| SNR | NumPy |
| Odd/even comparison | custom deterministic Python |
| Secondary eclipse | custom deterministic Python |
| P/2, P, 2P harmonic test | Astropy BLS + custom Python |
| Neighbor context | cached catalog data / HTTP lookup |
| Pixel contamination | high-value P1 after the core path; Lightkurve TPF + NumPy |
| Centroid | high-value P1 behind a cached-real acceptance gate; NumPy / SciPy |
| Uncertainty/tolerance | prioritize period comparison; preserve verified existing values; do not expand broadly |
| Static scientific plots | Matplotlib |
| Interactive scientific plots | Plotly |

## Development/deployment

- Python 3.12
- `uv`
- `pnpm`
- `pytest` + `pytest-asyncio`
- Ruff
- TypeScript + ESLint
- Git + GitHub
- GitHub Actions
- Vercel for frontend
- Railway for backend
- Docker for backend packaging
- deployment secrets via environment variables

## Do not add to the 48-hour core

- full LangChain abstraction stack,
- CrewAI or AutoGen,
- Redis,
- Celery,
- Kafka/RabbitMQ,
- Postgres/Supabase,
- vector database,
- GraphQL,
- WebSockets for the main stream,
- authentication,
- multiple providers,
- Kubernetes,
- microservices,
- arbitrary-target support,
- multi-sector stitching,
- full probabilistic exoplanet validation,
- extra 3D scenes or 3D scientific charts.

Multi-model routing is out of scope for the hackathon submission. Make the core reliable and
observable with one primary model.

The live provider path must report model identity, calls, input/output tokens, schema-valid/repair/
fallback counts, and latency from recorded call metadata. See `docs/inference.md`. Do not publish
estimated operational metrics as measurements.
