# Agent Harness Scaffold

This document records the bounded production-harness milestone. The control loop is operational
with live or scripted inference, deterministic science, durable execution, and explicit failure
boundaries.

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
| Model routing | One provider boundary; Featherless is configured when a nonblank key exists, with scripted clients injectable for tests/fallback |
| Loop control | One-cycle `advance()` invokes the sole LangGraph topology; guarded controller operations own policy, validation, execution, persistence, and stopping |
| Durable state | Atomic `state.json`; append-only `trace.jsonl` and Evidence Ledger writer |
| Context | Explicit agent-safe `AgentContextPacket` assembled from durable state |
| Output validation | Strict Pydantic models with forbidden extra fields and semantic validators |
| Retries | Bounded transient retry plus one schema/semantic repair; optional fallback is explicit and labeled |
| Tracing | Stable run, step, action, event IDs and monotonically ordered event envelopes |
| Recovery | State, trace, ledger, decisions, prepared/completed invocations, runner failures, and leases survive restart |
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
`COMPLETED`. A handler exception or invalid/mismatched result marks the invocation `FAILED` with a
failure class and concise reason in the same durable state update that terminates the run. Resume
reruns only a declared-idempotent `PREPARED` action when no result was committed; terminal failed
actions are never replayed.

Candidate search has a split input contract. Model-selectable `preprocessing` and `search` controls
are validated by the production registry. A backend-only `CandidateSourceResolver` supplies the
cached FITS path, while the controller derives the run artifact and Evidence Ledger paths. These
runtime inputs have their own strict schema, are combined only at invocation, and are not stored in
the execution record, trace, result parameters, or agent context. The science slice suppresses its
standalone ledger append on this controller-owned path so the harness remains the sole evidence
committer.

Candidate-dependent vetting receives no model-selected paths. The controller resolves the accepted
candidate artifact only from committed `search_bls` evidence in the same run, confines it to that
run's `artifacts/` directory, and injects it through strict runtime-only schemas. Contamination uses
typed cached neighbors when supplied; otherwise it may use the cached SPOC `CROWDSAP` header as an
explicitly labeled aggregate-capacity screen, never as source or centroid localization.

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

The default API loads a strict versioned opaque-target manifest from
`data/targets/source_manifest.json`. Missing mappings or cached files fail explicitly before
execution. Paths and identity-bearing provenance remain backend-only and are recursively rejected
from public state, event, and target payloads.

Result lock is a backend policy boundary. A run must be `READY_TO_LOCK` with a disposition and
terminal reason. The service writes exact canonical JSON bytes, hashes those bytes, updates durable
state, and only then makes catalog reveal eligible. The catalog gate re-verifies the hash before
calling a reveal provider.

## Human approval points

No current endpoint deploys, merges, deletes artifacts, or reveals catalog truth without a result
lock. Supplying `FEATHERLESS_API_KEY` enables model-provider contact for Skeptic/Critic only. The
real provider canary is credential-gated and never runs as part of ordinary offline tests.

## Final-stretch delta

The submission inference path is implemented. Next work should exercise the credential-gated live
canary, connect the mission-control UI to real SSE/state, add a contrasting cached target, and build
trajectory evaluations. The deterministic controller remains the Scientific Director authority.

Adaptive limits enforce both an experiment-count ceiling and deterministic cost units. Registry
specifications own action prices; durable state records configured, used, and remaining cost units;
and each `SkepticDecision` declares its observed remaining budget, selected cost, and concise cost
justification. The controller validates those declarations, applies a Critic revision's actual
registry price, and consumes units only in the durable `PREPARED` checkpoint. Recovery reuses that
checkpoint without charging again, and no-affordable-action termination is explicit.

Skeptic and Critic decisions are also bound to the packet context version as well as run and step
identifiers. Controller-local advances are single-writer, provider calls have enforced deadlines,
and production scientific handlers run in killable subprocesses. Candidate-producing tools write
to per-action staging and publish artifacts only after an on-time, validated result; timed-out or
cancelled work is terminated and its staging is discarded. Stale responses cannot prepare or
execute an action.

Do not expand this milestone into more model roles until the live Skeptic/Critic path and its
failure policy pass. Afterward, an Observer or Signal role is a valid P1 addition only when a test
shows that its bounded decision changes the scientific trajectory. Multi-model routing,
fixed-policy ablation, and `pass^3` remain out of scope.
