# API and SSE Contracts

The original planning context specifies FastAPI + REST + SSE but not exact endpoint paths. The paths and event names below are derived scaffold conventions.

## REST surface

### Health

`GET /health`

Returns application/service health only. No scientific fake data.

### List opaque demo targets

`GET /api/targets`

Returns only agent-safe, pre-reveal metadata, for example opaque IDs and data-availability flags. Do not expose real identity or known catalog disposition.

### Create investigation

`POST /api/investigations`

Requires a caller-generated `Idempotency-Key` header (1-128 characters). Reusing the same key and
target returns the same run; reusing it for another target returns a conflict.

Request:

```json
{
  "opaque_target_id": "TARGET-X17"
}
```

Returns `202`. The response contains `run_id`, opaque target ID, initial status, lock state,
event-stream URL, and the bounded runner execution snapshot.

### Resume investigation

`POST /api/investigations/{run_id}/resume`

Resumes a durable non-terminal run under the same per-run lease and returns `202` with state and
execution metadata. It never creates a second investigation.

### Read investigation

`GET /api/investigations/{run_id}`

Returns the agent-safe current structured state/view model. Once inference has occurred, include the
recorded run-level inference summary or an explicit scripted/unavailable state.

### Stream events

`GET /api/investigations/{run_id}/events`

Content type: `text/event-stream`.

### Lock result

`POST /api/investigations/{run_id}/lock`

Allowed only when deterministic runtime policy says the run is lock-eligible. Returns locked artifact metadata/hash.

### Reveal ground truth

`POST /api/investigations/{run_id}/reveal`

Must return an authorization/lock error before `RESULT_LOCKED`. After lock, creates/returns the reveal comparison.

### Artifact metadata

`GET /api/investigations/{run_id}/artifacts`

Returns references/metadata, not hidden ground truth before reveal.

## SSE event envelope

Every event should use one envelope:

```json
{
  "event_id": "evt_...",
  "run_id": "run_...",
  "step_id": "step_...",
  "sequence": 12,
  "timestamp": "2026-08-15T00:00:00Z",
  "type": "evidence.appended",
  "payload": {},
  "schema_version": "1"
}
```

Implemented event types:

- `investigation.created`
- `status.changed`
- `agent.started`
- `agent.decision`
- `inference.attempt`
- `inference.fallback`
- `inference.summary`
- `critic.review`
- `tool.started`
- `tool.completed`
- `tool.failed`
- `evidence.appended`
- `hypothesis.updated`
- `budget.updated`
- `model.retry`
- `recovery.completed`
- `result.locked`
- `catalog.revealed`
- `run.failed`

An `inference.attempt` payload is the sanitized typed trace record described in
`docs/inference.md`; repairs are identified by `attempt_kind=repair` rather than a second event
name.

Inference events expose model identity, role, attempt kind, latency, usage when supplied, validation
status, and fallback status. They must not expose prompt bodies, secrets, hidden reasoning, raw
samples, recognizable target identity, or catalog truth. The terminal `inference.summary` is
computed from the trace contract in `docs/inference.md`.

## Ordering and idempotency

- `sequence` is monotonically increasing per run.
- Every side-effecting action has an action ID.
- Duplicate/replayed events must not create duplicate irreversible actions.
- A reconnecting UI should be able to refetch current state and then continue the stream.
- A frontend refresh must not unlock ground truth or alter scientific state.

## Error payloads

Prefer typed errors:

```json
{
  "code": "RESULT_NOT_LOCKED",
  "message": "Ground-truth reveal is unavailable before result lock.",
  "run_id": "run_...",
  "recoverable": true
}
```

Scientific negative results remain scientific tool results, not HTTP 500 errors.

## Frontend rule

The frontend renders structured backend state/events. It does not calculate authoritative scientific measurements, invent progress, or infer the final disposition independently.
