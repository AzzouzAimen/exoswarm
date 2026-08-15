# Agent Harness Scaffold

This document records the mocked bounded-harness milestone. The control loop is operational with
scripted inference and deterministic fixture results; live provider configuration remains deferred.

## Harness boundary

The model is an optional decision component behind `agents/model_client.py`. It cannot execute
Python functions directly. The loop validates structured model output, resolves an allowlisted
action in `investigation/tool_registry.py`, enforces the tool specification, and only then invokes
deterministic science code.

Current surfaces:

| Surface | Scaffold implementation |
|---|---|
| Instructions | Repository contract plus role-specific adapter modules |
| Tools and schemas | Allowlisted `ScientificToolRegistry` and typed `ScientificToolResult` |
| Permissions | Side-effect and approval metadata on every registered tool |
| Model routing | One `InferenceClient` boundary plus queued `ScriptedInferenceClient`; live provider intentionally unconfigured |
| Loop control | One-cycle `advance()` with mandatory policy, Skeptic request, Critic review, validation, execution, update, and stopping |
| Durable state | Atomic `state.json`; append-only `trace.jsonl` and Evidence Ledger writer |
| Context | Explicit agent-safe `AgentContextPacket` assembled from durable state |
| Output validation | Strict Pydantic models with forbidden extra fields and semantic validators |
| Retries | Bounded transient model retry; validation and domain failures do not retry |
| Tracing | Stable run, step, action, event IDs and monotonically ordered event envelopes |
| Recovery | State, trace, ledger, decisions, and prepared/completed invocations reload after restart |
| Evaluation | Four branch scenarios plus schema, authorization, failure, context, restart, blind-protocol, result-lock, and API tests |

## Authority classes

- Locked: ground-truth mappings, catalog reveal provider, result-lock policy, and test/eval rules.
- Editable: role adapters, future prompts, registry entries, and deterministic implementations.
- Append-only: Evidence Ledger records and run traces.
- Human-controlled: secrets, deployment, merging, and destructive artifact operations.

The `agents` package has no import path to `services.nasa_reveal` or
`security.catalog_gate`; a structural test enforces this.

## State, recovery, and tracing

Each run is stored under `runs/<opaque-target-id>/<run-id>/`. State snapshots use atomic file
replacement. Trace and evidence records append JSONL. A new controller process can locate a run by
its run ID and reconstruct its snapshot, trace, and ledger. The loop checkpoints accepted decisions
and a `PREPARED` invocation before execution, then records matching evidence and marks it
`COMPLETED`. Resume reruns only a declared-idempotent prepared action when no result was committed.

## Approval and failure policy

Model output is a request, never authority. Schema, role/run/step identity, registry membership,
availability, strict parameters, scopes, preconditions, duplicate policy, mandatory/lock rules, and
budgets are checked before execution. Scientific stubs return typed `NOT_IMPLEMENTED` results with
empty measurements and provenance rather than invented data. Only transient model/provider failures
receive bounded retries in this milestone. Invalid output,
authorization denial, precondition failure, negative scientific evidence, and exhausted budgets
remain distinct states.

The model packet is rebuilt from durable state and compact Evidence Ledger records. It contains
opaque identity, evidence-linked measurements with units, completed checks, recent evidence,
hypotheses, validated adaptive actions, remaining budgets, and context/provenance versions. It
omits raw arrays, cached paths, recognizable identity, catalog/reveal data, and hidden reasoning.
Candidate measurements enter state only from matching deterministic ledger records.

Result lock is a backend policy boundary. A run must be `READY_TO_LOCK` with a disposition and
terminal reason. The service writes exact canonical JSON bytes, hashes those bytes, updates durable
state, and only then makes catalog reveal eligible. The catalog gate re-verifies the hash before
calling a reveal provider.

## Human approval points

No current scaffold endpoint deploys, merges, accesses secrets, deletes artifacts, or contacts a
catalog/model provider. Enabling those capabilities requires explicit configuration and a later
implementation task with its own tests and approval boundaries.
