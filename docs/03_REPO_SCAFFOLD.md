# Repository Scaffold Guide

This tree is a derived implementation convention for the supplied ExoSwarm architecture. Keep the first task focused on creating these boundaries, not filling every module with production logic.

## Target tree

```text
.
├── README.md
├── AGENTS.md
├── FIRST_AGENT_PROMPT.md
├── Makefile
├── .env.example
├── .gitignore
├── pnpm-workspace.yaml
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   └── ...architecture and contract docs...
├── .agents/
│   └── skills/
│       └── <skill-name>/SKILL.md
├── apps/
│   ├── web/
│   │   ├── package.json
│   │   ├── next.config.*
│   │   ├── tsconfig.json
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   └── src/
│   │       ├── components/
│   │       │   └── mission-control/
│   │       │       ├── MissionControlShell.tsx
│   │       │       ├── TargetStatus.tsx
│   │       │       ├── CentralOrbitScene.tsx
│   │       │       ├── ScientificPlotPanel.tsx
│   │       │       ├── HypothesisPanel.tsx
│   │       │       ├── AgentActivity.tsx
│   │       │       ├── EvidenceLedger.tsx
│   │       │       ├── AdaptiveDecisionPanel.tsx
│   │       │       └── LockRevealPanel.tsx
│   │       ├── lib/
│   │       │   ├── api.ts
│   │       │   ├── events.ts
│   │       │   └── contracts.ts
│   │       └── types/
│   └── api/
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── src/
│       │   └── exoswarm/
│       │       ├── __init__.py
│       │       ├── config.py
│       │       ├── domain/
│       │       │   ├── enums.py
│       │       │   ├── models.py
│       │       │   ├── events.py
│       │       │   └── errors.py
│       │       ├── science/
│       │       │   ├── contracts.py
│       │       │   ├── io.py
│       │       │   ├── preprocessing.py
│       │       │   ├── bls.py
│       │       │   ├── transit.py
│       │       │   ├── odd_even.py
│       │       │   ├── secondary.py
│       │       │   ├── harmonic.py
│       │       │   ├── centroid.py
│       │       │   └── plotting.py
│       │       ├── agents/
│       │       │   ├── model_client.py
│       │       │   ├── context.py
│       │       │   ├── graph.py
│       │       │   ├── director.py
│       │       │   ├── observer.py
│       │       │   ├── signal.py
│       │       │   ├── transit_hunter.py
│       │       │   ├── skeptic.py
│       │       │   └── critic.py
│       │       ├── investigation/
│       │       │   ├── state.py
│       │       │   ├── controller.py
│       │       │   ├── tool_registry.py
│       │       │   ├── mandatory.py
│       │       │   ├── hypotheses.py
│       │       │   ├── evidence.py
│       │       │   ├── stopping.py
│       │       │   └── persistence.py
│       │       ├── security/
│       │       │   ├── blinding.py
│       │       │   ├── result_lock.py
│       │       │   └── catalog_gate.py
│       │       ├── services/
│       │       │   ├── target_registry.py
│       │       │   ├── artifacts.py
│       │       │   └── nasa_reveal.py
│       │       └── api/
│       │           ├── app.py
│       │           ├── dependencies.py
│       │           ├── routes_health.py
│       │           ├── routes_investigations.py
│       │           └── sse.py
│       └── tests/
│           ├── test_schema_contracts.py
│           ├── test_tool_registry.py
│           ├── test_blind_protocol.py
│           ├── test_result_lock.py
│           └── test_api_smoke.py
├── data/
│   ├── README.md
│   ├── cached/
│   │   ├── lightcurves/.gitkeep
│   │   └── tpf/.gitkeep
│   ├── targets/
│   │   └── manifest.example.json
│   └── ground_truth/
│       └── README.md
├── runs/
│   └── .gitkeep
├── evals/
│   ├── README.md
│   ├── cases/.gitkeep
│   ├── fixtures/.gitkeep
│   └── report.md
└── scripts/
    ├── reproduce.py
    └── hash_result.py
```

## Backend dependency rules

Keep the low-level domain contracts importable without pulling in FastAPI, LangGraph, or science libraries.

Recommended direction:

```text
domain
  ^
  |------ science
  |------ agents
  |------ investigation
             ^
             |
         security/services
             ^
             |
             api
```

More important than the exact arrows are the authority constraints:

- `agents/` must not import `services/nasa_reveal.py`.
- `agents/` must not access real target mappings or catalog truth.
- `science/` must not call LLMs.
- `science/` returns structured results; it does not decide the high-level scientific disposition.
- `api/` is an adapter; scientific truth belongs in domain/investigation/science state, not route handlers.
- `web/` renders backend state and never calculates authoritative scientific values.

## Environment variable conventions

Derived scaffold names:

```text
EXOSWARM_ENV=development
EXOSWARM_MODEL=DeepSeek-V4-Flash-0731
FEATHERLESS_API_KEY=
FEATHERLESS_BASE_URL=
EXOSWARM_RUNS_DIR=./runs
EXOSWARM_DATA_DIR=./data
EXOSWARM_MAX_STEPS=12
EXOSWARM_MAX_ADAPTIVE_EXPERIMENTS=4
```

Do not put secrets or real credentials in the repository. The exact Featherless base URL is intentionally not hard-coded in this context pack.

## Scaffold behavior

The scaffold should be runnable but scientifically empty:

- health endpoint can return real application status,
- investigation creation can create a typed run ID/state,
- SSE can stream lifecycle test events,
- lock/reveal permission logic can be real,
- tool registry can reject unknown tools,
- science functions can be typed stubs that fail explicitly,
- frontend can render empty/loading/not-implemented states,
- no module should output fake periods, SNRs, depths, or centroids.

## Run artifact convention

Use:

```text
runs/<opaque-target-id>/<run-id>/
  state.json
  trace.jsonl
  result.json
  result.json.sha256
  reveal.json
  artifacts/
```

`reveal.json` must not exist until a locked result exists and reveal has been explicitly requested/authorized.
