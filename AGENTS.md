# AGENTS.md - ExoSwarm Coding-Agent Contract

This repository is designed to be edited by AI coding agents. Read this file before changing code.

## Source hierarchy

When instructions conflict, use this order:

1. Current user/task instructions.
2. This `AGENTS.md`.
3. `docs/15_FINAL_STRETCH_PRIORITIES.md` for remaining hackathon scope and sequencing.
4. `docs/00_SOURCE_OF_TRUTH.md` and the narrow architecture/contract document for the changed area.
5. Repository tests, schemas, and existing code contracts.
6. The relevant skill under `.agents/skills/`.
7. General implementation preference.

Do not invent scientific or product requirements to fill a gap. If a decision is not specified, choose the smallest reversible scaffold convention and document it.

## Judged-delivery priority

The judging panel is primarily enterprise software, cloud, data-platform, architecture, and
DevSecOps practitioners—not professional astronomers. Optimize remaining hackathon work for the
published scoring weight: Technical Execution & Architecture (20), Demo & Documentation (20),
Utility & Impact (10), and Originality (10).

Treat the six scored subcriteria as separate delivery gates: Code Structure & Quality (10), API &
Compute Integration (10), Innovation & Approach (10), Functional Execution (10), 3-Minute Video
Demo (10), and Documentation & Setup (10). A feature that cannot be demonstrated or explained does
not automatically improve the score merely because it is technically difficult.

Once the real backend/agent gates are green, prioritize clean boundaries, bounded model behavior,
observable decisions, recovery, security, repeatability, README clarity, and a polished end-to-end
demo. Do not spend judged-path time polishing specialist astronomy edge cases that require expert
domain knowledge to notice and do not change the honest product claim. Scientific correctness,
provenance, blinding, and deterministic numeric authority remain non-negotiable.

Do not casually rewrite a stabilized scientific or context-safety implementation merely because a
different formula or stricter keyword filter looks conventional. First read its narrow contract,
regression tests, and upstream-reference note; require a failing controlled/real case or a concrete
judged-path benefit before changing it.

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

For the remaining hackathon work, also do **not** spend time on fixed-policy ablations, `pass^3`,
large eval suites, new transit fitting, broad uncertainty propagation, or a separate LLM Scientific
Director. A real pixel/centroid diagnostic is optional, not a blocker: attempt it only after the
software architecture, agent observability, primary demo, and documentation gates are strong, and
only when it clearly improves the judged story. Retain an honest alternate-aperture/neighbor-context
fallback. Follow `docs/15_FINAL_STRETCH_PRIORITIES.md` for the current tiers and go/no-go rules.

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
- bug diagnosis -> `debugging-wizard`
- Harbor eval tasks, benchmark cases, or verifier design -> `eval-engineering`
- prompt design or structured model-output schemas -> `prompt-engineer`
- Python typing, async patterns, robust errors, or Python test tooling -> `python-pro`
- LangGraph code -> `langgraph-fundamentals`
- devil's-advocate review, pre-mortem, or red-team analysis -> `the-fool`
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
