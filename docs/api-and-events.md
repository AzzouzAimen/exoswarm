# API and SSE Contracts

FastAPI exposes the implemented REST control surface, UI-safe projections, and ordered SSE stream.

## REST surface

### Health

`GET /health`

Returns application/service health only. No scientific fake data.

### List opaque demo targets

`GET /api/targets`

Returns only agent-safe metadata, for example opaque IDs and data-availability flags. Do not expose real identity or known catalog disposition.

### List viewer references

`GET /api/viewer/targets`

`GET /api/viewer/targets/{opaque_target_id}`

Returns the human-viewer catalog projection: official identity, catalog disposition/source, and
known values. This projection is available before a run and must remain isolated from controller
state, agent context, SSE events, and scientific tools.

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

### Mission Control projection

`GET /api/investigations/{run_id}/mission-control`

Returns the typed UI projection assembled from durable backend state, evidence, decisions, and the
separate viewer reference. The viewer data is never merged back into investigation state.

`GET /api/investigations/{run_id}/mission-control/plots/{mode}`

Returns bounded Plotly-ready traces for an implemented scientific view. Unsupported modes and
unavailable evidence return explicit errors or empty states rather than fabricated points.

### Stream events

`GET /api/investigations/{run_id}/events`

Content type: `text/event-stream`.

### Legacy audit lock (not used by the primary UI)

`POST /api/investigations/{run_id}/lock`

Allowed only when deterministic runtime policy says the run is lock-eligible. Returns locked artifact metadata/hash.

### Legacy reproduction reveal (not used by the primary UI)

`POST /api/investigations/{run_id}/reveal`

Must return an authorization/lock error before `RESULT_LOCKED`. After lock, creates/returns the reveal comparison.

### Artifact metadata

`GET /api/investigations/{run_id}/artifacts`

Returns run artifact references/metadata; viewer catalog data uses the separate viewer route.

## SSE event envelope

Every event uses one envelope:

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
- `agent.queued`
- `agent.started`
- `agent.completed`
- `agent.handoff`
- `agent.skipped`
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
status, fallback status, prompt/example versions and hashes, context fingerprint, and separately
recorded thinking requested/confirmed fields. They must not expose prompt bodies, secrets, hidden
reasoning, raw samples, recognizable target identity, or catalog truth. The terminal
`inference.summary` is computed from the trace contract in `docs/inference.md`.

`agent.started` also exposes the sanitized `evidence_count` and `advisory_roles` visible to that
call. These fields make the promoted Director/Transit-Hunter-to-Skeptic handoff auditable while
confirming that the Critic receives no advisory-role context.

Validated and skipped role results are append-only records in `agent_decisions.jsonl`, which is
included in safe artifact metadata. A skipped record contains a stable fallback code and no model
decision. State exposes only role/phase/context checkpoints, preventing full role prose from
inflating every subsequent inference context.

## Ordering and idempotency

- `sequence` is monotonically increasing per run.
- Every side-effecting action has an action ID.
- Duplicate/replayed events must not create duplicate irreversible actions.
- A reconnecting UI should be able to refetch current state and then continue the stream.
- A frontend refresh must not alter scientific state or merge viewer reference data into run state.

## Error payloads

Domain errors use typed payloads:

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

The frontend renders structured backend state/events and the separate viewer projection. It does
not calculate authoritative scientific measurements, invent progress, or infer the scientific
disposition independently. A deterministic presentation adapter may compare the backend disposition
with the catalog class to produce the plain viewer verdict.
