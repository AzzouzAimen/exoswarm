# Agent Harness Scaffold

This document records the Phase 0 control boundary. It is operational architecture, not a
claim that the scientific investigation loop is implemented.

## Harness boundary

The model is an optional decision component behind `agents/model_client.py`. It cannot execute
Python functions directly. A future loop must validate structured model output, resolve an
allowlisted action in `investigation/tool_registry.py`, enforce the tool specification, and only
then invoke deterministic science code.

Current surfaces:

| Surface | Scaffold implementation |
|---|---|
| Instructions | Repository contract plus role-specific adapter modules |
| Tools and schemas | Allowlisted `ScientificToolRegistry` and typed `ScientificToolResult` |
| Permissions | Side-effect and approval metadata on every registered tool |
| Model routing | One `InferenceClient` boundary; live provider intentionally unconfigured |
| Loop control | Explicit status/budget fields; `advance()` fails as not implemented |
| Durable state | Atomic `state.json`; append-only `trace.jsonl` and Evidence Ledger writer |
| Context | Explicit agent-safe `AgentContextPacket` assembled from durable state |
| Output validation | Strict Pydantic models with forbidden extra fields and semantic validators |
| Retries | Per-tool retry metadata; execution policy deferred until the bounded loop exists |
| Tracing | Stable run, step, action, event IDs and monotonically ordered event envelopes |
| Recovery | Persisted state and trace reload on process-local cache miss |
| Evaluation | Schema, tool, blind-protocol, result-lock, and API boundary tests |

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
its run ID and reconstruct its current snapshot plus trace. The future investigation loop must
checkpoint after every accepted transition and use action IDs for idempotency.

## Approval and failure policy

Model output is a request, never authority. Unknown actions are rejected. Scientific stubs return
typed `NOT_IMPLEMENTED` results with empty measurements and provenance rather than invented data.
Only transient infrastructure failures may eventually receive bounded retries. Invalid output,
authorization denial, precondition failure, negative scientific evidence, and exhausted budgets
remain distinct states.

Result lock is a backend policy boundary. A run must be `READY_TO_LOCK` with a disposition and
terminal reason. The service writes exact canonical JSON bytes, hashes those bytes, updates durable
state, and only then makes catalog reveal eligible. The catalog gate re-verifies the hash before
calling a reveal provider.

## Human approval points

No current scaffold endpoint deploys, merges, accesses secrets, deletes artifacts, or contacts a
catalog/model provider. Enabling those capabilities requires explicit configuration and a later
implementation task with its own tests and approval boundaries.

