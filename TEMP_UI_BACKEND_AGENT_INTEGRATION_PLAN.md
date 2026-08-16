# ExoSwarm UI, Backend, and Agent Integration Plan

**Status:** Temporary implementation plan

**Scope:** Connect the existing mission-control frontend to the FastAPI investigation backend and bounded agent runtime without recreating pages, changing the visual design, or changing the user experience.

**Runtime decision:** Live backend integration is the default. The current fixture playback remains available only as an explicit offline/demo fallback.

**Primary constraint:** The frontend renders backend-owned investigation state and deterministic scientific evidence. It does not calculate authoritative measurements, invent progress, infer disposition, or bypass result-lock and catalog-reveal controls.

---

## 1. Objectives

The integration should make the existing mission-control interface show a real investigation from target selection through deterministic measurements, agent decisions, evidence updates, result locking, and post-lock catalog reveal.

The implementation must:

- Preserve the current page layout, typography, spacing, colors, motion, responsive behavior, component hierarchy, Plotly usage, and central React Three Fiber scene.
- Replace fixture-driven runtime state with live FastAPI state and SSE events.
- Keep deterministic Python science tools as the numerical authority.
- Make agent activity visible as concise structured decisions, handoffs, reviews, and statuses.
- Show real budgets, tool execution state, inference telemetry, failures, and recovery.
- Keep the target identity and catalog truth sealed until the backend has locked the result.
- Make refresh and reconnect safe and reconstructible from durable backend state.
- Retain fixture playback for explicit offline operation and frontend tests.
- Verify the end-to-end path on cached real TESS targets without requiring live astronomy-data access.

The implementation must not:

- Recreate the mission-control pages from scratch.
- Introduce a second frontend design system.
- Move scientific calculations into TypeScript.
- Add WebSockets, a second orchestration framework, a database, a message broker, or another model provider.
- Expose raw FITS data, local paths, recognizable target identities, catalog values, prompts, or hidden chain-of-thought.
- Add fabricated plot data or fallback scientific values to make a panel look complete.

---

## 2. Current Baseline

### 2.1 Frontend entrypoint

The application currently renders one page:

- `apps/web/app/page.tsx` renders `MissionControlShell`.
- `apps/web/app/layout.tsx` provides the application shell and global providers.
- `apps/web/app/globals.css` contains the current mission-control visual language.

The existing mission-control surface is already the intended UX baseline. It should remain the visible product while its data source changes.

### 2.2 Current runtime data flow

The current shell in `apps/web/src/components/mission-control/MissionControlShell.tsx`:

1. Selects a fixture target from `DEMO_CASES`.
2. Creates fixture state with `useDemoPlayback`.
3. Replays `PresentationEvent` objects through `demo-reducer.ts`.
4. Passes the resulting `InvestigationPresentationState` into the existing panels.
5. Uses a local boolean for reveal state.
6. Uses fixture result and fixture audit data for the result panel and integrity footer.

The current data producer is:

- `apps/web/src/components/mission-control/demo/use-demo-playback.ts`
- `apps/web/src/components/mission-control/demo/demo-reducer.ts`
- `apps/web/src/components/mission-control/demo/demo-cases.ts`
- `apps/web/src/components/mission-control/demo/demo-investigation.fixture.ts`

The current presentation consumer tree is:

- `MissionControlShell`
- `TargetStatus`
- `CentralOrbitScene`
- `TargetLaunchpad`
- `AgentTrace`
- `HypothesisPanel`
- `LockRevealPanel`
- `ScientificPlotPanel`
- `PlaybackControls`
- `RunIntegrity`
- `EvidenceLedger`
- `MobileInvestigationSheet`

This tree should remain intact. The integration should replace or wrap the data producer, not replace the presentation layer.

### 2.3 Existing frontend presentation boundary

`apps/web/src/components/mission-control/model/presentation-state.ts` already defines the main UI-facing model:

- agent identities and statuses,
- investigation phases,
- camera poses,
- instrument modes,
- evidence presentation,
- hypothesis presentation,
- Plotly trace presentation,
- instrument readouts,
- deterministic tool status,
- timeline records,
- investigation presentation state.

`demo-reducer.ts` already provides a useful event-to-state reducer. The live integration should either:

- normalize backend events into the existing `PresentationEvent` shape and reuse the reducer, or
- introduce a source-neutral reducer with the same output contract while keeping fixture replay tests intact.

The preferred approach is to preserve the existing reducer semantics and add a backend event adapter before it.

### 2.4 Existing frontend API helpers

`apps/web/src/lib/api.ts` currently contains:

- `getInvestigation(runId)`
- `createInvestigation(opaqueTargetId)`

`apps/web/src/lib/events.ts` currently contains `subscribeToInvestigation(runId, onEvent)`.

These helpers are currently unused by `MissionControlShell` and are incomplete for the live workflow. They do not currently provide:

- target listing,
- resume,
- lock,
- reveal,
- artifact metadata,
- mission-control projection,
- typed backend errors,
- sequence cursor handling,
- event deduplication,
- reconnect reconciliation.

### 2.5 Existing backend runtime

The backend already implements the main investigation lifecycle:

- `GET /health`
- `GET /api/targets`
- `POST /api/investigations`
- `POST /api/investigations/{run_id}/resume`
- `GET /api/investigations/{run_id}`
- `GET /api/investigations/{run_id}/events`
- `POST /api/investigations/{run_id}/lock`
- `POST /api/investigations/{run_id}/reveal`
- `GET /api/investigations/{run_id}/artifacts`

Relevant implementation files:

- `apps/api/src/exoswarm/api/routes_investigations.py`
- `apps/api/src/exoswarm/api/sse.py`
- `apps/api/src/exoswarm/investigation/runner.py`
- `apps/api/src/exoswarm/investigation/controller.py`
- `apps/api/src/exoswarm/investigation/state.py`
- `apps/api/src/exoswarm/investigation/persistence.py`
- `apps/api/src/exoswarm/domain/models.py`
- `apps/api/src/exoswarm/domain/events.py`
- `apps/api/src/exoswarm/domain/enums.py`

The run service owns process lifecycle, leases, timeout, and repeated graph advances. The controller owns guarded durable mutations and deterministic scientific policy. LangGraph is the investigation topology, not the durable source of truth.

### 2.6 Existing backend agent and science flow

The runtime can execute the documented bounded path:

1. Mandatory deterministic search and vetting.
2. Observer and Signal specialist briefings.
3. Transit Hunter briefing.
4. Director briefing.
5. Skeptic experiment selection.
6. Critic `APPROVE`, `REVISE`, or `VETO` review.
7. Deterministic tool execution.
8. Deterministic hypothesis update and stopping policy.
9. Director finalization where required.
10. `READY_TO_LOCK`.

The backend persists:

- `state.json`
- `trace.jsonl`
- `evidence.jsonl`
- `agent_decisions.jsonl`
- `inference_summary.json`
- `result.json`
- `result.json.sha256`
- `reveal.json` after explicit reveal
- science artifacts under `artifacts/`

The runtime uses bounded role outputs and does not persist hidden chain-of-thought.

### 2.7 Important current gaps

The live frontend cannot yet be connected honestly without addressing these gaps:

- `MissionControlShell` still consumes fixture cases and playback.
- The frontend does not call lock, reveal, resume, targets, or artifacts.
- The frontend event subscriber omits implemented event types such as `agent.queued`, `agent.completed`, `agent.handoff`, `agent.skipped`, and `hypothesis.updated`.
- The frontend status union omits backend `FINALIZING`.
- The public investigation state contains structured state but not a presentation-ready detailed evidence and plot view.
- `evidence.appended` identifies evidence but does not contain the measurements required by the evidence ledger and plot readouts.
- Artifact metadata is exposed, but safe artifact content is not exposed through the API.
- The current fixture panels contain recognizable catalog identities in client-side data and therefore cannot represent the live pre-reveal blind boundary.
- SSE supports `after_sequence`, but the current browser helper does not send a cursor or deduplicate replayed events.
- The stream closes when runner execution becomes inactive, including at `READY_TO_LOCK`; lock and reveal are separate REST actions that must be handled after the stream closes.
- Error payloads do not consistently include `run_id` even though the documented contract recommends it.
- CORS is currently hard-coded to `http://localhost:3000`.
- `RunIntegrity` and `LockRevealPanel` use fixture result data rather than backend state.

---

## 3. Target Architecture

The target architecture keeps the following direction of authority:

```text
Backend durable state and deterministic evidence
                 |
                 v
      Safe mission-control read model
                 |
          REST snapshot + SSE
                 |
                 v
      Frontend live investigation controller
                 |
       backend event normalization
                 |
                 v
  Existing presentation reducer/model boundary
                 |
                 v
       Existing mission-control components
```

The frontend will have three distinct layers:

### 3.1 Transport layer

Responsible for:

- REST requests,
- SSE connection lifecycle,
- request cancellation,
- typed errors,
- sequence cursors,
- reconnects,
- HTTP status handling.

Suggested location:

- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/events.ts`
- `apps/web/src/lib/contracts.ts`

### 3.2 Backend adapter layer

Responsible for:

- converting backend state into a safe frontend view,
- converting backend events into presentation events,
- mapping backend statuses to presentation phases,
- mapping backend roles and tool names to current UI labels,
- mapping measurements to readouts and evidence rows,
- converting deterministic plot projections into Plotly traces,
- handling incomplete and failed diagnostics without fabricating values.

Suggested location:

- `apps/web/src/components/mission-control/live/backend-adapter.ts`
- `apps/web/src/components/mission-control/live/live-reducer.ts` if a source-neutral reducer is needed.

### 3.3 Live investigation controller

Responsible for:

- target selection,
- run creation,
- run resume,
- initial snapshot loading,
- SSE subscription,
- buffered event history,
- live-follow mode,
- playback/scrubbing over buffered history,
- lock and reveal actions,
- refresh/reconnect recovery,
- explicit fallback selection.

Suggested location:

- `apps/web/src/components/mission-control/live/use-live-investigation.ts`
- or `apps/web/src/lib/mission-control/use-investigation-session.ts`.

The shell should consume a source-neutral controller result instead of knowing whether the source is live or fixture-based.

---

## 4. Integration Contracts

The integration should define contracts before implementation. Backend schemas remain authoritative, but the frontend should use explicit UI contracts rather than relying on loose `Record<string, unknown>` payloads.

### 4.1 Target contract

The target launchpad needs only safe pre-reveal metadata:

```ts
interface TargetOption {
  opaque_target_id: string
  cached_lightcurve_available: boolean
  cached_tpf_available: boolean
  sector?: string
  display_label?: string
}
```

Rules:

- `opaque_target_id` is the only identity available before reveal.
- `sector` is acceptable as non-recognizable observation metadata if supplied by the backend.
- No target name, TIC ID, TOI ID, catalog disposition, known period, or known depth may be present.
- The launchpad should show only targets returned by `GET /api/targets`.
- A target with unavailable source data should be visibly unavailable or excluded according to the existing launchpad behavior.

### 4.2 Investigation state contract

The existing `InvestigationView` should be expanded to include the fields the current UI needs:

```ts
interface InvestigationView {
  schema_version: "1"
  run_id: string
  opaque_target_id: string
  status: InvestigationStatus
  lock_state: LockState
  disposition: string | null
  terminal_reason: string | null
  completed_tests: string[]
  available_tests: string[]
  evidence_refs: string[]
  active_hypotheses: string[]
  strongest_unresolved_alternative: string | null
  unresolved_questions: string[]
  candidate_signals: CandidateSignalView[]
  accepted_decisions: SkepticDecisionView[]
  critic_decisions: CriticDecisionView[]
  role_checkpoints: RoleCheckpointView[]
  tool_executions: ToolExecutionView[]
  failures: FailureView[]
  inference_summary: InferenceSummaryView
  budgets: BudgetView
  execution: RunExecutionView
  updated_at: string
}
```

The frontend must support every backend status, including:

- `INITIALIZED`
- `PREPARING`
- `SEARCHING`
- `VETTING_MANDATORY`
- `SELECTING_ADAPTIVE_EXPERIMENT`
- `WAITING_FOR_CRITIC`
- `RUNNING_TOOL`
- `UPDATING_EVIDENCE`
- `FINALIZING`
- `READY_TO_LOCK`
- `RESULT_LOCKED`
- `REVEALED`
- `INSUFFICIENT_EVIDENCE`
- `REJECTED`
- `FAILED`
- `BUDGET_EXHAUSTED`

`FINALIZING` must not be presented as complete or lockable. It means the deterministic stopping reason is persisted and the finalization route is still being processed.

### 4.3 Evidence contract

Do not send raw `EvidenceRecord` objects directly to the browser. They include nested provenance and implementation fields that are not appropriate for the presentation boundary.

Define an explicit safe projection:

```ts
interface EvidenceView {
  evidence_id: string
  timestamp: string
  step_id: string
  action_id: string
  tool_name: string
  status: ToolStatus
  interpretation_code: string | null
  summary: string
  measurements: Record<string, MeasurementView>
  diagnostics: Record<string, string | number | boolean | null>
  method: string
  evidence_ref: string
  artifact_refs: string[]
}

interface MeasurementView {
  value: number | string | boolean
  display_value: string
  unit: string | null
  uncertainty: number | null
  tolerance: number | null
  evidence_ref: string
}
```

Rules:

- Every scientific number displayed by the UI must include an evidence or artifact reference.
- Units are supplied by the backend and are never guessed by the frontend.
- The frontend may format values for display but must not convert authoritative values or derive new measurements.
- Negative and indeterminate tool statuses remain visible as typed scientific outcomes.
- Local paths, cached filenames, source references, and private provenance must be removed or replaced with safe artifact identifiers.

### 4.4 Agent and reviewer contract

The UI needs a concise presentation projection of agent activity:

```ts
interface AgentCheckpointView {
  role: AgentId
  phase: "briefing" | "decision" | "review" | "final"
  status: "COMPLETE" | "SKIPPED"
  decision_id: string
  context_version: string
  evidence_refs: string[]
  summary: string
  action?: string
  expected_discriminator?: string
  model_identity?: string
  provider?: string
  latency_ms?: number
  schema_valid?: boolean
  fallback_code?: string
}
```

The UI may show:

- selected experiment,
- concise reason,
- expected discriminating result,
- Critic verdict,
- tool status,
- evidence references,
- model identity,
- measured latency and token values when available,
- skipped/fallback states.

The UI must not show:

- prompts,
- hidden reasoning,
- raw provider content,
- unbounded role prose,
- model-generated probability claims.

### 4.5 Budget contract

The existing `evidenceBudget` presentation field should be backed by durable state:

```ts
interface BudgetView {
  adaptive_cost_units_used: number
  adaptive_cost_units_remaining: number
  max_adaptive_cost_units: number
  adaptive_experiments_used: number
  max_adaptive_experiments: number
  model_call_count: number
  max_model_calls: number
  tool_call_count: number
  max_tool_calls: number
  critic_revision_count: number
  max_critic_revisions: number
  model_retry_count: number
  max_model_retries: number
}
```

The backend remains authoritative if a model-declared budget conflicts with durable state.

### 4.6 Inference summary contract

Use the backend `InferenceSummary` fields defined in `apps/api/src/exoswarm/domain/models.py` and `docs/inference.md`.

The UI should display:

- provider,
- model identity,
- model call count,
- token counts when measured,
- schema-valid rate,
- repair rate,
- fallback rate,
- provider error and timeout count,
- median latency,
- raw light-curve sample count sent to the model.

When a field is `not_measured`, the UI must display `not measured`, `unavailable`, or `scripted` according to the existing visual language. It must not substitute an illustrative number.

### 4.7 Plot contract

The backend should provide a safe plot projection rather than exposing arbitrary artifact files.

Recommended endpoints:

```text
GET /api/investigations/{run_id}/mission-control
GET /api/investigations/{run_id}/mission-control/plots/{mode}
```

The snapshot returns available plot modes and evidence references. The plot endpoint returns bounded Plotly-compatible data:

```ts
interface PlotView {
  mode: InstrumentMode
  available: boolean
  unavailable_reason?: string
  evidence_refs: string[]
  traces: Array<{
    name: string
    x: number[]
    y: number[]
    kind: "line" | "markers" | "bar"
    tone: "science" | "muted" | "unresolved" | "approved"
    dash?: "solid" | "dot" | "dash"
  }>
  x_label: string
  y_label: string
  annotation: string
  readouts: Array<{
    label: string
    value: string
    evidence_ref?: string
  }>
}
```

Plot rules:

- The backend owns all source data access and downsampling.
- The backend must enforce a maximum point count per trace.
- Downsampling must preserve extrema and candidate features where practical.
- A missing diagnostic returns `available: false`, not fake zeroes.
- Plot arrays must not be sent to agent contexts.
- Plot data may be requested lazily when a tab is selected to keep the main snapshot small.

---

## 5. Backend Work Plan

### Phase B0: Contract audit and test fixtures

Before changing implementation:

1. Capture representative backend payloads from:
   - a clean planet-like run,
   - an eclipsing-binary-like run,
   - an inconclusive run,
   - a model fallback or failure run,
   - a locked and revealed run.
2. Compare those payloads against `apps/web/src/lib/contracts.ts`.
3. Record field naming, optionality, enum values, timestamp format, and numeric types.
4. Add JSON fixtures for frontend adapter tests without adding identities or catalog payloads to pre-reveal fixtures.
5. Treat the current uncommitted UI changes as the presentation baseline; do not overwrite or revert them.

Acceptance checks:

- Every backend status has a frontend mapping.
- Every event type has a defined adapter behavior.
- Every existing panel has an identified live data source.
- No scientific display value is missing an evidence path.

### Phase B1: Add a backend-owned mission-control projection

Add a service responsible for projecting durable state and evidence into a UI-safe read model.

Suggested file:

- `apps/api/src/exoswarm/services/mission_control.py`

Responsibilities:

- Load `InvestigationState`.
- Load evidence from the append-only evidence ledger.
- Load agent decision records and inference summary.
- Load trace metadata when needed for the timeline.
- Resolve safe sector/data metadata without exposing target identity.
- Build hypotheses from deterministic state and interpretation codes.
- Build tool and agent summaries.
- Identify whether each plot mode is available.
- Build lock and reveal projections based on backend lock state.
- Remove local paths and private provenance fields.
- Enforce pre-reveal blinding.

Do not make the frontend assemble this projection from separate raw artifacts. That would duplicate backend rules and risk leaking fields.

Suggested response model location:

- `apps/api/src/exoswarm/api/mission_control_models.py`

Keep these models separate from agent context models. A UI projection is not an agent context packet.

### Phase B2: Add safe evidence and plot endpoints

Add routes in `apps/api/src/exoswarm/api/routes_investigations.py` or a dedicated mission-control route module.

Recommended routes:

```text
GET /api/investigations/{run_id}/mission-control
GET /api/investigations/{run_id}/mission-control/plots/{mode}
```

The snapshot route should return the current state and last event sequence. The plot route should validate the requested mode against a fixed allowlist:

- `raw`
- `bls`
- `phase-fold`
- `odd-even`
- `secondary`
- `harmonic`

The route must reject unknown modes rather than treating them as arbitrary artifact paths.

The backend should read science artifacts through a typed loader. Do not expose a generic `GET /artifacts/{path}` endpoint.

### Phase B3: Build deterministic plot projections

The existing candidate search artifact contains cleaned light curve, BLS grid, and phase-folded data. Build typed backend projection functions that:

- load only backend-owned artifacts,
- validate schema and hashes,
- decimate to a bounded point count,
- preserve units and conventions,
- attach evidence references,
- return unavailable states when the required tool has not executed.

For each mode:

#### Raw brightness

- Use cleaned light curve data from the candidate artifact.
- Return time in BTJD and relative flux as fraction.
- Include source and retained sample counts as readouts only if backed by evidence.
- Do not return the original FITS path.

#### BLS repeat search

- Use `period_grid_days` and `periodogram_depth_snr` from the candidate artifact.
- Mark the candidate period readout with the evidence reference from the BLS result.
- Preserve the period unit as days.

#### Phase fold

- Use the stored phase-folded arrays when present.
- Display phase convention explicitly in the annotation.
- Include period and depth readouts only when the corresponding measurements have evidence references.

#### Odd/even

- Use backend-generated diagnostic data if available.
- If only summary measurements are currently persisted, return a bounded bar/readout representation with the exact measured values and evidence references.
- Do not generate synthetic odd/even curves in the frontend.

#### Secondary event

- Use backend secondary diagnostic artifact or summary projection.
- Show an explicit no-evidence or indeterminate state when appropriate.

#### Harmonic

- Use measured half/current/double period diagnostics when the harmonic tool has executed.
- If it has not executed, keep the tab available only as an empty/unavailable instrument state rather than borrowing fixture values.

### Phase B4: Align backend event semantics

The backend currently emits many event types, including:

- `investigation.created`
- `status.changed`
- `director.route`
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
- `budget.updated`
- `model.retry`
- `recovery.completed`
- `result.locked`
- `catalog.revealed`
- `run.failed`

The documented contract also includes `hypothesis.updated`. Add or verify emission when deterministic evidence updates:

- active hypotheses,
- strongest unresolved alternative,
- interpretation code,
- disposition-relevant evidence.

The event payload should contain IDs, concise state, and evidence references. It should not duplicate full raw evidence or hidden model output.

Preserve the existing event envelope:

```json
{
  "event_id": "evt_...",
  "run_id": "run_...",
  "step_id": "step_0001",
  "action_id": "action_...",
  "sequence": 12,
  "timestamp": "2026-08-15T00:00:00Z",
  "type": "evidence.appended",
  "payload": {},
  "schema_version": "1"
}
```

Do not change event ordering or remove existing audit events solely for frontend convenience.

### Phase B5: Improve API errors and deployment configuration

Update the exception handler in `apps/api/src/exoswarm/api/app.py` so errors include:

```json
{
  "code": "RESULT_NOT_LOCKED",
  "message": "ground-truth reveal is unavailable before result lock",
  "run_id": "run_...",
  "recoverable": true
}
```

Include `run_id` when it can be recovered from the route or exception context.

Make CORS configurable using a settings field such as an allowlist of frontend origins. Keep localhost as the development default and document the deployed frontend origin configuration.

This is integration infrastructure, not a UI redesign.

### Phase B6: Make lock/reveal state refreshable

The backend currently writes `reveal.json` but the public read state does not contain the reveal comparison. Add a safe post-reveal projection so a refreshed browser can reconstruct the result panel.

Rules:

- Before `RESULT_LOCKED`, no catalog fields appear.
- At `RESULT_LOCKED`, the UI gets the lock receipt/hash but no catalog identity.
- After `POST /reveal`, the UI receives the catalog comparison and the locked hash.
- Subsequent `GET` snapshot calls can return the persisted reveal projection when the state is `CATALOG_REVEALED`.
- `result.json` remains immutable after reveal.
- Repeating reveal must not rewrite or mutate the locked result.

Add backend tests for refresh after reveal and same-run hash verification.

---

## 6. Frontend Work Plan

### Phase F0: Expand typed client contracts

Update `apps/web/src/lib/contracts.ts` to include:

- all backend investigation statuses,
- lock states,
- target options,
- run execution snapshots,
- candidate signals,
- measurements,
- evidence projections,
- role checkpoints,
- tool executions,
- failures,
- inference summaries,
- lock receipts,
- reveal results,
- mission-control snapshots,
- plot projections,
- typed API errors.

Avoid using `any`. Use `unknown` at the transport boundary and validate or narrow it before it enters the presentation model.

Use snake_case only at the API contract boundary. Convert to the frontend presentation naming convention in the adapter.

### Phase F1: Complete REST client helpers

Extend `apps/web/src/lib/api.ts` with typed functions:

```ts
listTargets()
createInvestigation(targetId, idempotencyKey?)
getInvestigation(runId)
getMissionControl(runId)
resumeInvestigation(runId)
lockInvestigation(runId)
revealInvestigation(runId)
listArtifacts(runId)
getInvestigationPlot(runId, mode)
```

Client behavior:

- Use `cache: "no-store"` for run state and reveal-sensitive requests.
- Generate and preserve an idempotency key per start attempt.
- Allow an optional caller-provided idempotency key for retrying the same create request.
- Parse typed error bodies and expose `code`, `message`, `run_id`, and `recoverable`.
- Abort stale requests when changing target or leaving the run.
- Never retry lock or reveal blindly. Reconcile state first when a request may have completed server-side.

### Phase F2: Replace the SSE helper with cursor-aware subscription

Update `apps/web/src/lib/events.ts`.

The subscriber should:

- accept `afterSequence`,
- append the cursor as a query parameter,
- register every implemented backend event type,
- parse the common envelope,
- ignore malformed events with an explicit error callback,
- deduplicate by `event_id` and `sequence`,
- expose `onOpen`, `onError`, and `onClose` hooks,
- close cleanly on unmount or run change.

Because browser `EventSource` does not allow arbitrary headers, use the existing `after_sequence` query parameter. Optionally add backend support for `Last-Event-ID`, but do not depend on custom headers from the browser.

Reconnect behavior:

1. Keep the highest accepted sequence in memory.
2. On disconnect, refetch the mission-control snapshot.
3. Compare snapshot `last_sequence` with the local cursor.
4. Recreate the SSE connection with `after_sequence=<highest accepted sequence>`.
5. Reconcile any missed events from the snapshot before rendering the live tail.
6. Deduplicate replayed events.

Do not treat an intentional stream close at `READY_TO_LOCK` as a network failure. The run service can become inactive before the separate lock request.

### Phase F3: Create the backend-to-presentation adapter

Add a single adapter responsible for mapping backend data to `InvestigationPresentationState`.

The adapter should provide:

```ts
function presentationFromSnapshot(snapshot: MissionControlSnapshot): InvestigationPresentationState

function presentationEventFromBackendEvent(
  event: InvestigationEvent,
  snapshot: MissionControlSnapshot,
): PresentationEvent | null

function mergeBackendEvent(
  state: InvestigationPresentationState,
  event: InvestigationEvent,
): InvestigationPresentationState
```

The adapter must not calculate scientific values. It may:

- choose labels,
- map enums to visual phases,
- format timestamps,
- select which backend measurement is shown in an existing readout,
- choose an existing camera pose based on backend status/evidence state,
- summarize structured role decisions into concise UI copy.

It must not:

- derive a period from arrays,
- calculate depth percentages,
- decide whether a disposition is planetary,
- infer a hypothesis from prose,
- create a probability,
- fabricate a plot if a backend plot is unavailable.

### Phase F4: Map backend lifecycle to existing visual phases

Use a deterministic, centralized mapping. Suggested initial mapping:

| Backend status or event state | Existing presentation phase |
|---|---|
| `INITIALIZED`, `PREPARING` | `observing` |
| `SEARCHING` | `observing` |
| `VETTING_MANDATORY` | `measuring` |
| candidate signal available | `candidate` or `characterizing` |
| `SELECTING_ADAPTIVE_EXPERIMENT` | `challenging` |
| `WAITING_FOR_CRITIC` | `reviewing` |
| `RUNNING_TOOL` | `testing` or `measuring` |
| `UPDATING_EVIDENCE` | `testing` |
| `FINALIZING` | `locking` |
| `READY_TO_LOCK` | `locking` |
| `RESULT_LOCKED` | `locked` |
| `REVEALED` | `locked` |
| `INSUFFICIENT_EVIDENCE` | `locking` with inconclusive result state |
| `REJECTED` | `locked` only after result lock; otherwise terminal-safe state |
| `FAILED`, `BUDGET_EXHAUSTED` | terminal failure presentation state |

The exact camera and stage mapping should be implemented in one function and tested. Components should not independently interpret backend statuses.

### Phase F5: Map each backend event to the existing timeline

The current `AgentTrace` and `EvidenceLedger` consume `TimelineRecord`. Normalize backend events into that model.

Recommended mappings:

| Backend event | Presentation effect |
|---|---|
| `investigation.created` | initialize run timeline and sealed target state |
| `status.changed` | update phase, stage label, terminal reason, and current question |
| `director.route` | append concise deterministic routing record with authority boundary |
| `agent.queued` | mark role waiting/queued and store objective metadata |
| `agent.started` | set role active and populate provider/model/evidence count metadata |
| `agent.completed` | mark role complete and attach decision/evidence references |
| `agent.skipped` | mark role complete/skipped with explicit fallback code |
| `agent.decision` | update role summary, selected action, cited evidence, and model metadata |
| `agent.handoff` | create existing handoff record from source role to destination node |
| `inference.attempt` | update inference telemetry and role inspector; do not render raw output |
| `inference.fallback` | append model fallback record and mark fallback telemetry |
| `inference.summary` | update run integrity/inference summary state |
| `critic.review` | update Critic role and review verdict |
| `tool.started` | set deterministic tool to running, update budget, and focus instrument |
| `tool.completed` | mark tool complete, attach evidence reference, and request evidence refresh |
| `tool.failed` | mark tool failed and preserve typed failure reason |
| `evidence.appended` | append evidence summary after loading safe evidence detail |
| `hypothesis.updated` | update hypothesis state and evidence references |
| `budget.updated` | update evidence budget and integrity counts |
| `model.retry` | append retry telemetry without showing hidden content |
| `recovery.completed` | append recovery record and reconcile state |
| `result.locked` | show lock hash and enable explicit reveal action |
| `catalog.revealed` | update revealed comparison after backend confirmation |
| `run.failed` | show terminal failure state and stop live follow |

Unknown future backend events should be retained in an audit-safe generic timeline record or ignored with telemetry, but they must not crash the run view.

### Phase F6: Implement the live investigation hook

Add a hook that exposes a source-neutral controller API to the shell.

Suggested responsibilities:

```ts
interface InvestigationController {
  mode: "live" | "fixture"
  status: "idle" | "loading" | "running" | "ready_to_lock" | "locked" | "revealed" | "failed"
  state: InvestigationPresentationState
  step: number
  totalSteps: number
  isPlaying: boolean
  error: ClientError | null
  start(targetId: string): Promise<void>
  resume(runId: string): Promise<void>
  setPlaying(value: boolean): void
  setStep(value: number): void
  replay(): void
  lock(): Promise<void>
  reveal(): Promise<void>
  reset(): void
}
```

Live state behavior:

- `start` creates a backend run and enters live follow mode.
- `resume` loads durable state before reconnecting to SSE.
- `setPlaying(false)` pauses local follow/scrub behavior only; it does not pause backend execution.
- `setStep` scrubs buffered events and stops live follow until the user returns to the latest step.
- New SSE events remain buffered while the UI is scrubbed.
- `replay` clears only the local presentation cursor and replays buffered events; it must not create a new backend investigation.
- `reset` closes transport, clears local run state, and returns to target selection.
- `lock` calls the backend only after `READY_TO_LOCK` and updates the view from the receipt.
- `reveal` calls the backend only after `RESULT_LOCKED` and displays the returned catalog projection.

The hook should use `useEffect` for transport lifecycle and preserve stable callback behavior according to the existing React conventions in the repository. Avoid adding broad memoization without evidence that it is needed.

### Phase F7: Wire `MissionControlShell` without redesign

Change only the data-source integration in `MissionControlShell`.

The shell should:

1. Load target options from the backend in live mode.
2. Pass those options into the existing launchpad presentation.
3. Start a live investigation on the existing Start button.
4. Pass live presentation state into the same existing panels.
5. Pass backend lock/reveal state into the existing result panel.
6. Pass backend counts and inference summary into the existing integrity footer.
7. Keep existing loading, selecting, running, terminal, and mobile layout behavior.

The shell should not contain:

- event type switches,
- scientific unit logic,
- backend status mapping,
- evidence parsing,
- lock authorization logic,
- catalog identity filtering.

Those belong in the transport, adapter, or backend authority layer.

### Phase F8: Adapt fixture-only props while preserving UI

Several current components accept `DemoCaseDefinition` or `DemoRunResult`. Replace those data-specific props with source-neutral view models while retaining their JSX and CSS structure.

Expected prop boundary changes:

#### `TargetLaunchpad`

Current source: `DEMO_CASE_LIST`.

Target source: `TargetOption[]`.

Preserve:

- target selector layout,
- sealed identity label,
- sector display,
- start action,
- fast-demo visual language.

The mode label should be derived from the controller mode rather than hard-coded to fixture playback in live mode.

#### `LockRevealPanel`

Current source: `DemoCaseDefinition`, local reveal boolean, fixture audit download.

Target source:

- final disposition,
- terminal reason,
- evidence references,
- lock receipt,
- reveal availability,
- reveal comparison,
- artifact/audit metadata.

Preserve:

- result heading,
- safe stop state,
- sealed official record state,
- compare button,
- post-reveal comparison table,
- audit accordion,
- restart action.

The download action must export backend-provided audit metadata or a backend-authorized artifact, not a locally assembled fixture report.

#### `RunIntegrity`

Current source: fixture agent/tool counts.

Target source:

- `inference_summary.agent_calls`,
- durable tool call count,
- provider/model identity,
- measured telemetry status,
- zero raw-sample invariant.

Preserve the current compact footer presentation.

#### `ScientificPlotPanel`

Keep the current component and Plotly settings. Replace fixture instrument data with `InstrumentPresentation` from the backend adapter. Do not change chart ownership from Plotly.

#### `PlaybackControls`

Keep the visual controls. Change labels only if needed so they describe buffered investigation playback rather than a fake backend pause. `Play` means follow the live tail; `Pause` means inspect the buffered trace.

#### `TargetStatus`

Replace the fixture flag with a source/status indicator that truthfully says live or offline fallback. Continue to show only opaque target identity before reveal.

### Phase F9: Add explicit runtime mode selection

Use a public frontend environment variable, for example:

```text
NEXT_PUBLIC_EXOSWARM_DATA_MODE=live
```

Supported values:

- `live`: use FastAPI and SSE; recommended default.
- `fixture`: use current fixture playback for offline presentation and tests.

Do not silently fall back from `live` to `fixture` after an API or model failure. A live failure must remain visible as a real backend failure. The offline mode must be selected explicitly for a clean demo fallback.

This keeps the current fixture system useful without allowing fixture values to masquerade as live scientific results.

---

## 7. Event and State Lifecycle

### 7.1 Target selection

1. Frontend loads `GET /api/targets` on entering selection mode.
2. The launchpad displays only safe opaque target metadata.
3. Target selection remains local until Start is clicked.
4. The frontend creates a fresh idempotency key for the start operation.
5. The backend validates the target mapping before creating the run.

### 7.2 Run creation

1. Frontend sends `POST /api/investigations` with `opaque_target_id` and `Idempotency-Key`.
2. Backend returns `run_id`, target ID, initial status, lock state, event URL, and execution snapshot.
3. Frontend stores the run ID immediately.
4. Frontend fetches the mission-control snapshot.
5. Frontend starts SSE from the snapshot's `last_sequence`.
6. Existing UI changes from selection to investigation stage.

### 7.3 Active investigation

The backend remains responsible for progressing the run. The frontend:

- renders the latest durable state,
- appends accepted events to the local trace buffer,
- updates the agent trace,
- updates deterministic tool state,
- requests safe evidence detail after evidence events,
- requests or receives plot data when instrument modes are selected,
- updates the evidence budget,
- renders failures and recovery.

The frontend must not send commands to select or execute agent tools. The agent runtime and deterministic controller own that flow.

### 7.4 Ready to lock

When the backend reports `READY_TO_LOCK`:

- the stream may close because the run service is no longer active,
- the UI should show that the result is ready but not yet committed,
- the frontend may enable the existing result action,
- the lock request must go to `POST /lock`,
- the frontend must not compute or hash the result itself.

The preferred user experience is to invoke lock from the existing completion flow after backend readiness is confirmed. The UI must not call lock early and rely on the backend error as normal flow.

### 7.5 Result lock

After a successful lock:

- update state to `RESULT_LOCKED`,
- store the SHA-256 receipt,
- display the committed timestamp and hash,
- keep catalog identity sealed,
- enable the existing Compare with official record action.

The hash displayed by the UI must come from `LockReceipt.sha256` or the authoritative `result.locked` event.

### 7.6 Reveal

On explicit user action:

1. Frontend calls `POST /reveal`.
2. Backend verifies the locked result bytes and persisted hash.
3. Backend invokes the catalog gate.
4. Backend writes `reveal.json`.
5. Backend returns the reveal comparison tied to the same run and locked hash.
6. Frontend updates the comparison table and target status.

The frontend must not call a catalog service directly.

### 7.7 Refresh and reconnect

On browser refresh or a component remount:

1. Restore only the opaque `run_id` and mode from local session state if supported.
2. Fetch the mission-control snapshot.
3. Render the snapshot before opening SSE.
4. Resume the backend only if the state is nonterminal and execution is paused/inactive for a recoverable reason.
5. Subscribe after the snapshot sequence.
6. Reconcile duplicate events.

Refresh must not:

- create a second run,
- execute a duplicate lock,
- execute a duplicate reveal,
- unlock ground truth,
- change the scientific result.

---

## 8. Security and Scientific Invariants

These are release-blocking invariants.

### 8.1 Blind target identity

Before `RESULT_LOCKED`, no API response, SSE payload, browser state, or live-mode client asset may expose:

- target name,
- TIC ID,
- TOI ID,
- recognizable catalog identity,
- known catalog disposition,
- known period/depth/duration values from the catalog,
- private source paths,
- cached FITS filenames,
- local file URLs.

The frontend can show:

- opaque target ID,
- safe sector/observation metadata,
- run ID,
- current status,
- lock state,
- deterministic measurements from the investigation evidence.

### 8.2 Deterministic numeric authority

Every visible numeric scientific value must be traceable to:

- an evidence ID,
- a measurement field,
- an artifact reference,
- or a backend-derived telemetry field.

The frontend may format `0.0099079` as `0.99%` only if the backend contract explicitly defines that display conversion. It must not infer percentages based on field names.

### 8.3 Agent boundary

The UI may render sanitized decision fields and telemetry. It must never render:

- full prompts,
- hidden reasoning,
- raw model messages,
- raw light-curve samples as agent context,
- catalog information included by mistake.

### 8.4 Lock authority

Only the backend result-lock service can:

- construct the locked result,
- canonicalize the bytes,
- compute the SHA-256,
- persist `RESULT_LOCKED`,
- authorize reveal.

The frontend is only a caller and renderer.

### 8.5 Failure truthfulness

Do not convert these into fake progress or successful panels:

- missing data,
- tool failure,
- precondition failure,
- model timeout,
- invalid model output,
- fallback,
- rejected signal,
- insufficient evidence,
- budget exhaustion,
- run timeout,
- recovery failure.

Each must remain a typed state or timeline event with a concise user-facing explanation.

---

## 9. Testing and Verification Plan

Follow the repository's layered verification order.

### 9.1 Backend unit and contract tests

Add tests for:

- mission-control response schema,
- plot mode allowlist,
- bounded plot point count,
- numeric units and evidence references,
- unavailable plot state,
- safe pre-reveal projection,
- safe post-reveal projection,
- hypothesis event emission,
- error payload `run_id`,
- configurable CORS origins,
- reveal persistence after refresh.

Relevant existing test location:

- `apps/api/tests/test_api_smoke.py`
- `apps/api/tests/test_schema_contracts.py`
- `apps/api/tests/test_blind_protocol.py`
- `apps/api/tests/test_result_lock.py`
- `apps/api/tests/test_cached_backend_gate.py`
- `apps/api/tests/test_run_service.py`

### 9.2 Frontend transport tests

Add tests for:

- `listTargets`,
- create request and idempotency key,
- typed error parsing,
- resume,
- lock,
- reveal,
- plot loading,
- abort behavior,
- SSE event parsing,
- event cursor query construction,
- duplicate event suppression,
- malformed event handling,
- reconnect callback behavior.

### 9.3 Frontend adapter tests

Add tests that map representative backend state/events to the existing presentation model:

- initial sealed run,
- search tool running,
- candidate measurements available,
- Skeptic decision selected,
- Critic approved,
- Critic revised,
- Critic vetoed,
- tool failure,
- model fallback,
- skipped optional role,
- insufficient evidence,
- budget exhausted,
- finalizing,
- ready to lock,
- locked,
- revealed.

Assertions should verify:

- correct phase,
- correct active agent,
- correct tool state,
- evidence references preserved,
- no fabricated instrument values,
- lock hash only appears after lock,
- catalog identity only appears after reveal.

### 9.4 Existing fixture regression tests

Keep the current tests for:

- demo reducer replay,
- agent trace stage construction,
- fixture case terminal state,
- fixture blindness assertions.

The fixture reducer is still valuable as a presentation test source even after live mode becomes the default.

### 9.5 Backend cached end-to-end tests

Exercise at minimum:

- `TARGET-C11` or `TARGET-P21` for a planet-like path,
- `TARGET-B42` for an eclipsing-binary-like path,
- `TARGET-D31` for an inconclusive path.

For each path verify:

- target creation,
- durable state progression,
- SSE sequence ordering,
- mandatory deterministic evidence,
- branch-specific completed tests,
- final disposition or inconclusive status,
- lock behavior where applicable,
- reveal denial before lock,
- reveal hash equality after lock,
- no pre-lock catalog leakage.

### 9.6 Frontend browser smoke tests

Run the live UI against a local backend and verify:

1. Target list loads.
2. Target selection preserves the current launchpad appearance.
3. Start creates exactly one backend run.
4. Agent trace updates from real events.
5. Scientific plot tabs load only available backend data.
6. Evidence ledger updates with backend evidence IDs.
7. Pause/scrub/rejoin behavior works on buffered events.
8. A tool failure remains visible.
9. `READY_TO_LOCK` does not reveal catalog identity.
10. Lock displays the backend hash.
11. Reveal displays catalog comparison only after explicit action.
12. Refresh after reveal reconstructs the comparison.
13. Mobile layout remains usable.
14. The central R3F scene remains nonblank and responds to phase changes.

Use the expected desktop demo viewport and at least one mobile viewport.

### 9.7 Required commands

Run the narrowest checks first, then the full checks:

```bash
uv run --project apps/api --extra science --extra agents pytest -c apps/api/pyproject.toml
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
pnpm --dir apps/web lint
pnpm --dir apps/web build
make eval-real-tess
make reproduce
make build
```

For a live provider gate when credentials are available:

```bash
uv run --project apps/api --extra science --extra agents python scripts/run_live_backend_gate.py
```

Do not claim live provider verification when only scripted or cached tests were run.

---

## 10. Delivery Phases and Checkpoints

### Delivery 1: Contract and projection foundation

Deliver:

- typed frontend contracts,
- backend mission-control response model,
- safe evidence projection,
- initial target and run snapshot wiring,
- backend contract tests.

Checkpoint:

- Frontend can load a real target and render a sealed initial state using the existing layout.

### Delivery 2: Live event timeline

Deliver:

- cursor-aware SSE,
- event normalization,
- live reducer/controller,
- real agent/tool/evidence timeline,
- duplicate and reconnect handling.

Checkpoint:

- A live cached run updates `AgentTrace` and `EvidenceLedger` without fixture playback.

### Delivery 3: Real scientific panel data

Deliver:

- safe plot projection,
- lazy plot loading,
- evidence-backed readouts,
- unavailable/indeterminate states,
- live hypothesis mapping.

Checkpoint:

- Plotly receives backend-provided structured values for the modes that actually ran, and no fake values for modes that did not run.

### Delivery 4: Agent observability and adaptive decisions

Deliver:

- role checkpoint mapping,
- Skeptic decision display,
- Critic review display,
- selected experiment and cost,
- inference summary,
- fallback/retry/skipped-role states.

Checkpoint:

- A model-assisted cached run visibly shows the bounded agent path and deterministic tool boundary.

### Delivery 5: Lock and reveal

Deliver:

- backend lock helper,
- backend reveal helper,
- lock receipt state,
- persisted post-reveal state,
- backend audit export or safe artifact action,
- refreshed lock/reveal UI state.

Checkpoint:

- Ground truth remains unavailable until backend result lock, and reveal verifies the exact locked hash.

### Delivery 6: Explicit offline fallback

Deliver:

- `live` default mode,
- explicit `fixture` mode,
- clear mode indicator,
- fixture regression preservation.

Checkpoint:

- Offline presentation works without being mistaken for a live backend run.

### Delivery 7: End-to-end hardening

Deliver:

- refresh/reconnect tests,
- failure-path tests,
- mobile and desktop browser smoke checks,
- cached reproduction verification,
- documentation updates after implementation.

Checkpoint:

- The primary judged path completes three consecutive times from a clean reset with valid science, lock, blind boundary, and reveal behavior.

---

## 11. File-Level Change Map

### Backend files expected to change or be added

Potential additions:

- `apps/api/src/exoswarm/api/mission_control_models.py`
- `apps/api/src/exoswarm/services/mission_control.py`
- `apps/api/src/exoswarm/science/plot_projection.py`

Potential updates:

- `apps/api/src/exoswarm/api/routes_investigations.py`
- `apps/api/src/exoswarm/api/app.py`
- `apps/api/src/exoswarm/investigation/controller.py`
- `apps/api/src/exoswarm/domain/events.py` if event typing is expanded
- `apps/api/src/exoswarm/services/artifacts.py` for typed safe reads only
- `apps/api/src/exoswarm/config.py` for CORS/runtime options
- relevant backend tests under `apps/api/tests/`

### Frontend files expected to change or be added

Potential additions:

- `apps/web/src/components/mission-control/live/backend-adapter.ts`
- `apps/web/src/components/mission-control/live/use-live-investigation.ts`
- `apps/web/src/components/mission-control/live/live-types.ts` if not kept in `lib/contracts.ts`
- frontend transport and adapter fixtures under `apps/web/src/lib/__tests__/` or the existing component test locations

Potential updates:

- `apps/web/src/lib/contracts.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/events.ts`
- `apps/web/src/components/mission-control/MissionControlShell.tsx`
- `apps/web/src/components/mission-control/TargetLaunchpad.tsx`
- `apps/web/src/components/mission-control/LockRevealPanel.tsx`
- `apps/web/src/components/mission-control/RunIntegrity.tsx`
- `apps/web/src/components/mission-control/TargetStatus.tsx`
- `apps/web/src/components/mission-control/PlaybackControls.tsx` only where live-follow semantics need truthful labels
- existing mission-control tests

The expected changes are data-boundary changes. The visual component structure and styling should remain intact.

---

## 12. Risks and Mitigations

### Risk: Backend state is too large for the initial frontend payload

Mitigation:

- Return compact mission-control state.
- Load plot arrays lazily.
- Return decimated bounded traces.
- Never send raw source arrays to agent or general UI state.

### Risk: SSE closes at `READY_TO_LOCK` and is interpreted as failure

Mitigation:

- Inspect execution and durable status after stream close.
- Treat `READY_TO_LOCK` as an expected terminal-for-runner state.
- Transition to lock-ready UI state rather than reconnecting indefinitely.

### Risk: Reconnect duplicates timeline records

Mitigation:

- Deduplicate by `event_id` and sequence.
- Refetch state before reconnect.
- Use `after_sequence` from the highest accepted event.

### Risk: Fixture data leaks into live pre-reveal assets

Mitigation:

- Keep live and fixture runtime paths separate.
- Use explicit fixture mode.
- Avoid importing fixture reveal objects into the live production component path when possible.
- Add bundle/content blind checks for live mode.

### Risk: Frontend displays plausible but unsupported scientific values

Mitigation:

- Require evidence references in the UI view model.
- Render unavailable states instead of fallback numbers.
- Do not let the frontend compute derived scientific values.
- Test every displayed readout against a backend measurement reference.

### Risk: Agent event payloads become long or expose hidden reasoning

Mitigation:

- Use concise backend projections.
- Display only structured decision fields and concise reasons.
- Do not render raw event payloads wholesale.

### Risk: Lock/reveal race during refresh or repeated clicks

Mitigation:

- Disable action while request is pending.
- Reconcile current backend state before retry.
- Treat an already locked/revealed response as an idempotent success where appropriate.
- Never locally set `revealed = true` without a successful backend response.

### Risk: Current frontend modifications conflict with integration work

Mitigation:

- Inspect the current worktree before each edit.
- Preserve unrelated user changes.
- Keep integration edits limited to data contracts, adapters, transport, and minimal prop boundaries.
- Do not reset or rewrite existing mission-control UI changes.

---

## 13. Out of Scope

The following are explicitly excluded from this integration:

- Rebuilding the mission-control page.
- Changing the visual design or UX flow.
- Adding a chat interface.
- Adding new 3D scientific charts.
- Moving Plotly charts into R3F.
- Letting the frontend execute science tools directly.
- Letting the frontend choose agent actions.
- Allowing the frontend to read catalog data before lock.
- Adding broad arbitrary-target support.
- Adding a vector database or RAG system.
- Adding authentication.
- Adding WebSockets for the primary stream.
- Adding another LLM provider.
- Adding a second orchestration framework.
- Implementing speculative centroid or pixel science as part of the first integration pass.

---

## 14. Final Acceptance Criteria

The integration is complete when all of the following are true:

- The existing mission-control UI renders a real backend investigation by default.
- Fixture playback is available only through explicit offline/demo configuration.
- Target selection uses backend `GET /api/targets`.
- Start creates one idempotent backend run.
- Resume reconstructs the same durable investigation.
- SSE updates the existing timeline and panels with ordered, deduplicated events.
- Reconnect and refresh do not duplicate irreversible effects.
- Agent roles, Skeptic selection, Critic review, tools, and handoffs are visible as concise structured state.
- Inference telemetry comes from backend trace records.
- Deterministic tools remain the source of every scientific number.
- Plotly receives bounded backend plot projections with units and evidence references.
- Missing or failed diagnostics remain visibly unavailable or failed rather than fabricated.
- `FINALIZING` is distinguishable from `READY_TO_LOCK`.
- Lock hash and timestamp come from the backend result-lock service.
- Catalog identity and known values remain sealed before result lock.
- Reveal is possible only through the backend catalog gate.
- Post-reveal refresh reconstructs the comparison from persisted backend state.
- Pre-reveal API and SSE payloads pass blinding checks.
- Clean planet-like, eclipsing-binary-like, and inconclusive cached paths remain distinct.
- Frontend tests, typecheck, lint, and production build pass.
- Backend tests and cached reproduction pass.
- The desktop and mobile layouts remain visually and behaviorally consistent with the current UI baseline.
- The primary demo path completes successfully three consecutive times from a clean reset.

---

## 15. Recommended Execution Order

Implement in this order:

1. Add and test the backend mission-control projection.
2. Expand frontend typed contracts.
3. Complete REST helpers and typed error handling.
4. Add cursor-aware SSE and deduplication.
5. Implement snapshot-to-presentation and event-to-presentation adapters.
6. Add the live investigation hook.
7. Wire `MissionControlShell` to the source-neutral hook.
8. Replace fixture-only props in launchpad, integrity, and lock/reveal panels while preserving markup and styles.
9. Add safe plot projections and lazy instrument loading.
10. Add lock/reveal and post-refresh persistence behavior.
11. Add explicit fixture fallback mode.
12. Run layered tests and cached end-to-end verification.
13. Harden the exact judged path.
14. Update README and integration documentation with tested commands and limitations.

The first milestone should stop after a real opaque target can be selected, a backend run can be created, and the current UI can render the initial sealed state. Subsequent milestones should add evidence and agent observability incrementally so each boundary remains testable and reversible.
