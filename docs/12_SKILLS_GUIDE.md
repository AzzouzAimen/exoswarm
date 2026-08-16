# Coding-Agent Skills Guide

The repository includes the supplied skills under `.agents/skills/<name>/SKILL.md`. Use the narrowest skill that owns the task.

| Skill | Use when |
|---|---|
| `reference-exoplanet-projects` | locating and safely adapting indexed SHERLOCK/WATSON, ASTER, or Stargazer code, fixtures, architecture, and evaluation patterns |
| `engineer-agent-system` | choosing/redesigning agent topology, deterministic vs model boundaries, state/routing/approvals/failure architecture |
| `engineer-agent-harness` | instructions, tool permissions, model routing, persistence, validation, tracing, recovery, approval boundaries |
| `engineer-agent-loop` | loop states, retries, budgets, termination, idempotency, resumability, repeated-action protection |
| `engineer-agent-context` | context packets, JIT retrieval, trimming, provenance, context isolation, compaction/staleness |
| `design-agent-tools` | tool names, schemas, permissions, result payloads, typed failures, side effects, token efficiency |
| `langgraph-fundamentals` | writing any LangGraph code, including `StateGraph`, nodes, edges, `Command`, `Send`, invocation, streaming, or error handling |
| `evaluate-agent-system` | scenario suites, trace metrics, deterministic graders, baselines, regression/release gates |
| `eval-engineering` | Harbor tasks, agent evals, benchmark cases, verifier design, or controlled agent environments |
| `prompt-engineer` | prompt design/refactoring, structured outputs, rubrics, few-shot examples, or prompt evaluation |
| `orchestrate-investigation` | ExoSwarm investigation state, evidence-dependent branching, experiment selection, Critic review, stopping, catalog lock |
| `implement-science-tool` | deterministic TESS/BLS/transit/odd-even/secondary/harmonic/centroid numerical implementation |
| `validate-science` | scientific fixtures, tolerances, units, positive/negative cases, cached-real-data regression |
| `build-mission-control-ui` | mission-control frontend, scientific plots, evidence board, timeline, viewer reference, and result-comparison UI |
| `verify-integration` | cross-layer state/schema/unit/event/lock verification after a change |
| `debugging-wizard` | concrete errors, stack traces, logs, crashes, or unexpected runtime behavior; isolate the root cause before fixing |
| `python-pro` | Python 3.11+ implementation where typing, async behavior, robust errors, pytest, mypy, black, or ruff are central |
| `the-fool` | devil's-advocate review, pre-mortems, red teaming, or audits of assumptions and proposals |
| `harden-demo` | only after core works; repeatability, reset, cached/offline path, model failure, judged runtime |
| `implement-feature` | a non-trivial feature not owned by a narrower ExoSwarm skill |

## Initial scaffold task

The first scaffold should primarily consult:

1. `engineer-agent-system`
2. `engineer-agent-harness`
3. `engineer-agent-loop`
4. `engineer-agent-context`
5. `design-agent-tools`
6. `implement-feature` only for generic scaffold plumbing that is not owned by the narrower architecture skills

Use `orchestrate-investigation`, `implement-science-tool`, `build-mission-control-ui`, and evaluation skills for contract awareness, but do not prematurely implement their full feature scope during the scaffold.

## Important cross-skill rules

Across all skills:

- upstream projects are advisory references below ExoSwarm docs, tests, schemas, and local skill contracts,
- machine-enforce invariants when possible,
- structured state beats conversational memory,
- deterministic code owns measurements and policies that can be expressed reliably,
- model outputs that drive code must be validated,
- tools fail explicitly and return decision-useful context,
- context is a finite attention budget,
- loops must be bounded and observable,
- traces should make behavior debuggable without hidden chain-of-thought,
- tests should cover negative/failure paths, not only the happy path,
- completion claims require verification evidence.

`langgraph-fundamentals` is a code-specific skill and does not change ExoSwarm's architecture rule against introducing a second orchestration framework for the core path. Use it only when LangGraph code is explicitly in scope.
