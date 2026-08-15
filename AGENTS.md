# AGENTS.md - ExoSwarm Coding-Agent Contract

This repository is designed to be edited by AI coding agents. Read this file before changing code.

## Source hierarchy

When instructions conflict, use this order:

1. Current user/task instructions.
2. This `AGENTS.md`.
3. `docs/00_SOURCE_OF_TRUTH.md` and the narrow architecture/contract document for the changed area.
4. Repository tests, schemas, and existing code contracts.
5. The relevant skill under `.agents/skills/`.
6. General implementation preference.

Do not invent scientific or product requirements to fill a gap. If a decision is not specified, choose the smallest reversible scaffold convention and document it.

## Non-negotiable architecture

- Models choose or review **bounded scientific actions**; deterministic Python owns measurements.
- Never let an LLM infer numerical scientific measurements from plots, prose, or raw samples.
- Mandatory diagnostics are explicit code paths, not optional model suggestions.
- Adaptive experiments come from a bounded registry and are validated before execution.
- The Skeptic can select an adaptive experiment; the Critic reviews it with APPROVE / REVISE / VETO.
- Agent-visible context uses opaque target IDs and compact evidence packets.
- Ground truth and recognizable target identity remain gated until a locked result exists.
- Evidence is append-only and provenance-aware.
- The outer investigation loop is explicit, bounded, inspectable, and has terminal reasons.
- Do not persist or expose hidden chain-of-thought. Persist structured decisions and concise reasons only.
- Do not show model-generated confidence percentages as scientific probability.
- Every scientific numeric value shown in the UI must be traceable to deterministic evidence.

## Scope discipline

For the 48-hour core, do **not** add:

- a second orchestration framework,
- Redis/Celery/Kafka/RabbitMQ,
- Postgres/Supabase,
- a vector database or RAG layer,
- GraphQL,
- WebSockets for the main event stream,
- authentication,
- microservices,
- Kubernetes,
- multiple LLM providers,
- broad arbitrary-target support,
- multi-sector stitching,
- full probabilistic exoplanet validation,
- extra 3D scientific charts.

Use one FastAPI backend, REST + SSE, local cached inputs, JSON/JSONL artifacts, and one central React Three Fiber scene.

## Dependency boundaries

Maintain these directional boundaries:

```text
domain/models, domain/enums
        ^
        |
science -------- investigation -------- agents
        \             |                  |
         \            v                  v
          ------ evidence/tool contracts/context
                         |
                         v
                  api + SSE adapters

security/result_lock + security/catalog_gate are backend authority boundaries.
Agent modules must not import the ground-truth/reveal implementation.
Frontend never becomes a source of scientific truth.
```

The exact package layout is in `docs/03_REPO_SCAFFOLD.md`.

## Skill routing

Use the narrowest applicable skill. The skill index is in `docs/12_SKILLS_GUIDE.md`.

Examples:

- upstream SHERLOCK/WATSON, ASTER, or Stargazer reference selection and code index -> `reference-exoplanet-projects`
- architecture/topology -> `engineer-agent-system`
- harness, permissions, tracing -> `engineer-agent-harness`
- runtime loop/budgets/recovery -> `engineer-agent-loop`
- context packets/compaction -> `engineer-agent-context`
- tool schemas/permissions -> `design-agent-tools`
- scientific numerical tool -> `implement-science-tool`
- scientific validation -> `validate-science`
- investigation orchestration -> `orchestrate-investigation`
- mission-control frontend -> `build-mission-control-ui`
- cross-layer verification -> `verify-integration`
- bug diagnosis -> `debug-systematically`
- demo reliability after core works -> `harden-demo`
- broad feature with no narrower owner -> `implement-feature`
- agent evals -> `evaluate-agent-system`

Do not edit the skill files unless the user explicitly asks.

## Working method

Before implementation:

1. Read the relevant code and narrow docs.
2. State the contract: inputs, outputs, errors, state changes, acceptance checks.
3. Keep the change as small as the task allows.
4. Add or update tests at the boundary being changed.
5. Run the narrowest checks first, then broader integration checks.
6. Report exact verification; do not claim completion without evidence.

When a failure exists, diagnose the root cause before refactoring.

## Scaffold-specific rule

If the task is the initial repository scaffold, create package/module boundaries, typed schemas, interfaces, test skeletons, configuration, and minimal smoke paths. Do **not** implement the full scientific algorithms, live model calls, live NASA/MAST fetches, or fake scientific demo values during the scaffold task.
