# ExoSwarm Documentation

The root [README](../README.md) is the fastest route to the product, local setup, architecture
diagram, verification commands, limitations, and citations. These documents describe the
implemented system in more detail.

## Product and architecture

- [Project overview](project-overview.md) — problem, users, claims, and falsification-first approach
- [Architecture](architecture.md) — components, authority boundaries, topology, and failure model
- [Technology](technology.md) — implemented stack and the reason each layer exists
- [Mission Control UI](mission-control-ui.md) — information hierarchy and scientific presentation

## Agent and API contracts

- [Agent harness](agent-harness.md) — permissions, validation, recovery, and durable execution
- [Agent runtime](agent-runtime.md) — roles, state, budgets, decisions, and context packets
- [Featherless inference](inference.md) — provider integration, structured outputs, traces, and canaries
- [API and events](api-and-events.md) — REST endpoints, SSE envelope, ordering, and errors

## Science and verification

- [Science contracts](science-contracts.md) — deterministic measurements, units, and failure semantics
- [Data and blinding](data-and-blinding.md) — cached inputs, evidence ledger, identity isolation, and lock
- [Scientific provenance](scientific-provenance.md) — TESS processing and upstream adaptation record
- [Upstream inspirations and attribution](upstream-inspirations.md) — pinned references, licenses,
  adopted ideas, and explicit exclusions
- [Testing and evaluation](testing-and-evaluation.md) — regression layers, locked suites, and release gates

Generated evaluation evidence lives under [`evals/`](../evals/README.md). Cached-data provenance and
the backend-only catalog boundary are documented under [`data/`](../data/README.md).
