import type {
  AgentCheckpointView,
  AgentRole,
  EvidenceView,
  InvestigationEvent,
  InvestigationStatus,
  MissionControlSnapshot,
  PlotMode,
  PlotView,
  ToolExecutionView,
} from "@/lib/contracts"

import { applyPresentationEvent } from "../demo/demo-reducer"
import type {
  AgentId,
  AgentPresentation,
  CameraPose,
  EvidencePresentation,
  InstrumentMode,
  InstrumentPresentation,
  InvestigationPhase,
  InvestigationPresentationState,
  PresentationEvent,
  SemanticTone,
  TimelineRecord,
  ToolPresentation,
} from "../model/presentation-state"

const AGENT_DEFINITIONS: Array<Pick<AgentPresentation, "id" | "label" | "function">> = [
  { id: "director", label: "Director", function: "Orchestrates bounded checks" },
  { id: "observer", label: "Observer", function: "Checks data quality" },
  { id: "signal", label: "Signal", function: "Finds repeats" },
  { id: "transit_hunter", label: "Transit", function: "Measures the dips" },
  { id: "skeptic", label: "Skeptic", function: "Tests other causes" },
  { id: "critic", label: "Critic", function: "Approves safe checks" },
]

const INSTRUMENT_LABELS: Record<InstrumentMode, string> = {
  raw: "Brightness over time",
  bls: "Period search",
  "phase-fold": "Dips lined up",
  "odd-even": "Alternating dip check",
  secondary: "Hidden companion check",
  harmonic: "Alternative periods",
}

const TOOL_MODES: Record<string, InstrumentMode> = {
  search_bls: "bls",
  odd_even: "odd-even",
  secondary_eclipse: "secondary",
  harmonic_test: "harmonic",
}

export interface StatusPresentation {
  phase: InvestigationPhase
  stageIndex: number
  stageLabel: string
  currentQuestion: string
  cameraPose: CameraPose
  terminal: boolean
}

export function presentationForStatus(status: InvestigationStatus): StatusPresentation {
  switch (status) {
    case "INITIALIZED":
    case "PREPARING":
      return { phase: "observing", stageIndex: 1, stageLabel: "Prepare", currentQuestion: "Is the observation ready?", cameraPose: "field", terminal: false }
    case "SEARCHING":
      return { phase: "observing", stageIndex: 2, stageLabel: "Search", currentQuestion: "Do the brightness dips repeat?", cameraPose: "field", terminal: false }
    case "VETTING_MANDATORY":
      return { phase: "measuring", stageIndex: 3, stageLabel: "Measure", currentQuestion: "Does the candidate pass required checks?", cameraPose: "measurement", terminal: false }
    case "SELECTING_ADAPTIVE_EXPERIMENT":
      return { phase: "challenging", stageIndex: 4, stageLabel: "Challenge", currentQuestion: "Which bounded check best separates the alternatives?", cameraPose: "alternatives", terminal: false }
    case "WAITING_FOR_CRITIC":
      return { phase: "reviewing", stageIndex: 5, stageLabel: "Review", currentQuestion: "Is the proposed check valid and useful?", cameraPose: "alternatives", terminal: false }
    case "RUNNING_TOOL":
      return { phase: "testing", stageIndex: 6, stageLabel: "Run check", currentQuestion: "What does deterministic measurement return?", cameraPose: "measurement", terminal: false }
    case "UPDATING_EVIDENCE":
      return { phase: "testing", stageIndex: 7, stageLabel: "Save evidence", currentQuestion: "How does the measured evidence change the open alternatives?", cameraPose: "measurement", terminal: false }
    case "FINALIZING":
      return { phase: "locking", stageIndex: 8, stageLabel: "Finalize", currentQuestion: "Is the bounded investigation ready to conclude?", cameraPose: "lock", terminal: false }
    case "READY_TO_LOCK":
      return { phase: "locking", stageIndex: 9, stageLabel: "Result ready", currentQuestion: "How does the independent result compare with the viewer reference?", cameraPose: "lock", terminal: true }
    case "RESULT_LOCKED":
      return { phase: "locked", stageIndex: 10, stageLabel: "Result ready", currentQuestion: "Independent result and viewer reference are available", cameraPose: "lock", terminal: true }
    case "REVEALED":
      return { phase: "locked", stageIndex: 10, stageLabel: "Result ready", currentQuestion: "Independent result and viewer reference are available", cameraPose: "lock", terminal: true }
    case "INSUFFICIENT_EVIDENCE":
      return { phase: "locking", stageIndex: 9, stageLabel: "Safe stop", currentQuestion: "Evidence remains insufficient", cameraPose: "lock", terminal: true }
    case "REJECTED":
      return { phase: "locking", stageIndex: 9, stageLabel: "Rejected", currentQuestion: "The tested interpretation was rejected", cameraPose: "lock", terminal: true }
    case "FAILED":
      return { phase: "locking", stageIndex: 9, stageLabel: "Run failed", currentQuestion: "The failure remains recorded", cameraPose: "lock", terminal: true }
    case "BUDGET_EXHAUSTED":
      return { phase: "locking", stageIndex: 9, stageLabel: "Budget exhausted", currentQuestion: "The bounded run reached its limit", cameraPose: "lock", terminal: true }
  }
}

export function unavailableInstrument(
  mode: InstrumentMode = "raw",
  reason = "This measurement is not available for the current run.",
): InstrumentPresentation {
  return {
    mode,
    label: INSTRUMENT_LABELS[mode],
    available: false,
    unavailableReason: reason,
    plot: { traces: [], xLabel: "", yLabel: "", annotation: reason },
    readouts: [],
  }
}

export function instrumentFromPlot(plot: PlotView): InstrumentPresentation {
  return {
    mode: plot.mode,
    label: INSTRUMENT_LABELS[plot.mode],
    available: plot.available,
    ...(!plot.available ? { unavailableReason: plot.unavailable_reason ?? plot.annotation } : {}),
    plot: {
      traces: plot.traces.map((trace) => ({
        name: trace.name,
        x: trace.x,
        y: trace.y,
        kind: trace.kind,
        tone: trace.tone,
        ...(trace.dash ? { dash: trace.dash } : {}),
      })),
      xLabel: plot.x_label,
      yLabel: plot.y_label,
      annotation: plot.annotation,
    },
    readouts: plot.readouts.map((readout) => ({
      label: readout.label,
      value: readout.value,
      ...(readout.evidence_ref ? { evidenceRef: readout.evidence_ref } : {}),
    })),
  }
}

function checkpointAgent(checkpoint: AgentCheckpointView | undefined, definition: typeof AGENT_DEFINITIONS[number]): AgentPresentation {
  const skipped = checkpoint?.status === "SKIPPED"
  return {
    ...definition,
    status: checkpoint ? "complete" : "waiting",
    summary: checkpoint?.summary ?? (skipped ? `Skipped: ${checkpoint?.fallback_code ?? "safe baseline"}` : "Idle"),
    inspector: {
      currentQuestion: checkpoint?.summary ?? "No active question",
      evidenceRefs: checkpoint?.evidence_refs ?? [],
      action: checkpoint?.action ?? "none",
      expectedDiscriminator: checkpoint?.expected_discriminator ?? "not selected",
      model: [checkpoint?.provider, checkpoint?.model_identity].filter(Boolean).join(" · ") || "not measured",
      latency: checkpoint?.latency_ms == null ? "not measured" : `${checkpoint.latency_ms} ms`,
      schema: checkpoint?.schema_valid == null ? "pending" : checkpoint.schema_valid ? "valid" : "pending",
    },
  }
}

function evidencePresentation(item: EvidenceView): EvidencePresentation {
  const measurement = Object.values(item.measurements)[0]
  return {
    id: item.evidence_id,
    kind: item.interpretation_code ?? item.tool_name,
    sourceTool: item.tool_name,
    summary: item.summary,
    ...(measurement && typeof measurement.value === "number"
      ? { measurement: { value: measurement.value, displayValue: measurement.display_value, unit: measurement.unit ?? "" } }
      : {}),
    supports: [],
    contradicts: [],
    provenance: item.evidence_ref,
  }
}

function toolPresentation(item: ToolExecutionView): ToolPresentation {
  return {
    name: item.tool_name,
    status: item.status === "PREPARED" ? "running" : item.status === "FAILED" ? "failed" : "complete",
    ...(item.evidence_ref ? { evidenceRef: item.evidence_ref } : {}),
    authority: "deterministic",
  }
}

function record(
  id: string,
  sequence: number,
  timestamp: string,
  values: Omit<TimelineRecord, "id" | "sequence" | "timestamp">,
): TimelineRecord {
  return { id, sequence, timestamp, ...values }
}

function durableTimeline(snapshot: MissionControlSnapshot): TimelineRecord[] {
  const status = presentationForStatus(snapshot.status)
  const items: Array<Omit<TimelineRecord, "sequence">> = [{
    id: `status-${snapshot.status}`,
    timestamp: snapshot.updated_at,
    eventType: "audit.event",
    boundary: "authority",
    agentId: "director",
    actor: "DIRECTOR CONTROL",
    headline: status.stageLabel,
    detail: snapshot.terminal_reason ?? snapshot.status,
    tone: snapshot.status === "FAILED" || snapshot.status === "BUDGET_EXHAUSTED" ? "danger" : "neutral",
  }]
  for (const checkpoint of snapshot.role_checkpoints) {
    items.push({
      id: `checkpoint-${checkpoint.role}-${checkpoint.phase}-${checkpoint.context_version}-${checkpoint.decision_id}`,
      timestamp: snapshot.updated_at,
      eventType: checkpoint.status === "SKIPPED" ? "audit.event" : "agent.decision",
      boundary: "agent",
      agentId: checkpoint.role,
      actor: checkpoint.role.toUpperCase(),
      headline: checkpoint.status === "SKIPPED" ? "Role skipped safely" : `${checkpoint.phase} complete`,
      detail: checkpoint.summary ?? checkpoint.fallback_code ?? checkpoint.decision_id,
      tone: checkpoint.status === "SKIPPED" ? "unresolved" : "model",
    })
  }
  for (const decision of snapshot.accepted_decisions) {
    items.push({
      id: `skeptic-${decision.decision_id}`,
      timestamp: snapshot.updated_at,
      eventType: "agent.decision",
      boundary: "agent",
      agentId: "skeptic",
      actor: "SKEPTIC",
      headline: decision.requested_experiment,
      detail: decision.concise_reason,
      tone: "model",
      evidenceRef: decision.supporting_evidence_refs[0],
    })
  }
  for (const decision of snapshot.critic_decisions) {
    items.push({
      id: `critic-${decision.decision_id}`,
      timestamp: snapshot.updated_at,
      eventType: "critic.review",
      boundary: "review",
      agentId: "critic",
      actor: "CRITIC",
      headline: decision.verdict,
      detail: decision.concise_reason,
      tone: decision.verdict === "APPROVE" ? "approved" : "unresolved",
      evidenceRef: decision.supporting_evidence_refs[0],
    })
  }
  for (const execution of snapshot.tool_executions) {
    const tool = toolPresentation(execution)
    items.push({
      id: `tool-${execution.action_id}`,
      timestamp: snapshot.updated_at,
      eventType: execution.status === "PREPARED" ? "tool.started" : "tool.completed",
      boundary: "code",
      tool,
      actor: "SCIENCE TOOL",
      headline: execution.status === "FAILED" ? `${execution.tool_name} failed` : execution.tool_name,
      detail: execution.failure_reason ?? execution.result_status ?? execution.status,
      tone: execution.status === "FAILED" ? "danger" : "science",
      evidenceRef: execution.evidence_ref ?? undefined,
    })
  }
  for (const evidence of snapshot.evidence) {
    items.push({
      id: `evidence-${evidence.evidence_id}`,
      timestamp: evidence.timestamp,
      eventType: "evidence.appended",
      boundary: "evidence",
      actor: "EVIDENCE",
      headline: evidence.summary,
      detail: `${evidence.tool_name} · ${evidence.status}`,
      tone: evidence.status === "FAILED" ? "danger" : "science",
      evidenceRef: evidence.evidence_id,
    })
  }
  for (const [index, failure] of snapshot.failures.entries()) {
    items.push({
      id: `failure-${failure.step_id}-${index}`,
      timestamp: snapshot.updated_at,
      eventType: "audit.event",
      boundary: "authority",
      actor: "RUNTIME",
      headline: failure.kind,
      detail: failure.concise_reason,
      tone: "danger",
    })
  }
  if (snapshot.lock.sha256 && snapshot.lock.locked_at) {
    items.push({
      id: `lock-${snapshot.lock.sha256}`,
      timestamp: snapshot.lock.locked_at,
      eventType: "result.locked",
      boundary: "authority",
      actor: "AUTHORITY",
      headline: "Independent result saved",
      detail: snapshot.lock.sha256,
      tone: "approved",
    })
  }
  if (snapshot.reveal) {
    items.push({
      id: `reveal-${snapshot.reveal.revealed_at}`,
      timestamp: snapshot.reveal.revealed_at,
      eventType: "audit.event",
      boundary: "authority",
      actor: "CATALOG GATE",
      headline: "Official record revealed",
      detail: snapshot.reveal.catalog_source,
      tone: "approved",
    })
  }
  const ids = new Set<string>()
  return items
    .filter((item) => {
      if (ids.has(item.id)) return false
      ids.add(item.id)
      return true
    })
    .map((item, index) => record(item.id, index + 1, item.timestamp, item))
}

function activeRole(status: InvestigationStatus): AgentId | undefined {
  if (status === "SELECTING_ADAPTIVE_EXPERIMENT") return "skeptic"
  if (status === "WAITING_FOR_CRITIC") return "critic"
  if (status === "FINALIZING") return "director"
  return undefined
}

function modeFromSnapshot(snapshot: MissionControlSnapshot): InstrumentMode {
  const active = [...snapshot.tool_executions].reverse().find((item) => item.status === "PREPARED")
  if (active && TOOL_MODES[active.tool_name]) return TOOL_MODES[active.tool_name]
  const available = snapshot.available_plot_modes.find((mode): mode is PlotMode => mode in INSTRUMENT_LABELS)
  return available ?? "raw"
}

export function presentationFromSnapshot(snapshot: MissionControlSnapshot): InvestigationPresentationState {
  const status = presentationForStatus(snapshot.status)
  const latestCheckpoints = new Map<AgentRole, AgentCheckpointView>()
  for (const checkpoint of snapshot.role_checkpoints) latestCheckpoints.set(checkpoint.role, checkpoint)
  const activeAgentId = activeRole(snapshot.status)
  const agents = AGENT_DEFINITIONS.map((definition) => {
    const agent = checkpointAgent(latestCheckpoints.get(definition.id), definition)
    return definition.id === activeAgentId ? { ...agent, status: "active" as const } : agent
  })
  const hypotheses = snapshot.active_hypotheses.map((id) => ({
    id,
    label: id.replaceAll("_", " ").replaceAll("-", " "),
    state: id === snapshot.strongest_unresolved_alternative ? "under-test" as const : "unresolved" as const,
    evidenceRefs: snapshot.evidence_refs,
    note: id === snapshot.strongest_unresolved_alternative ? "Strongest unresolved alternative" : "Backend-tracked hypothesis",
  }))
  if (snapshot.strongest_unresolved_alternative && !hypotheses.some((item) => item.id === snapshot.strongest_unresolved_alternative)) {
    hypotheses.push({
      id: snapshot.strongest_unresolved_alternative,
      label: snapshot.strongest_unresolved_alternative.replaceAll("_", " ").replaceAll("-", " "),
      state: "under-test",
      evidenceRefs: snapshot.evidence_refs,
      note: "Strongest unresolved alternative",
    })
  }
  const activeExecution = [...snapshot.tool_executions].reverse().find((item) => item.status === "PREPARED")
  const instrumentMode = modeFromSnapshot(snapshot)
  return {
    run: { id: snapshot.run_id, mode: "live", status: snapshot.status, terminalReason: snapshot.terminal_reason },
    target: {
      id: snapshot.opaque_target_id,
      sector: "Sealed observation",
      dataLabel: "API investigation",
      groundTruthState: snapshot.reveal ? "revealed" : "sealed",
    },
    ...status,
    activeAgentId,
    agents,
    hypotheses,
    evidence: snapshot.evidence.map(evidencePresentation),
    ...(activeExecution ? { activeTool: toolPresentation(activeExecution) } : {}),
    instrument: unavailableInstrument(instrumentMode),
    evidenceBudget: { used: snapshot.budgets.adaptive_cost_units_used, total: snapshot.budgets.max_adaptive_cost_units },
    timeline: durableTimeline(snapshot),
    ...(snapshot.lock.sha256 && snapshot.lock.locked_at
      ? { lock: { hash: snapshot.lock.sha256, lockedAt: snapshot.lock.locked_at } }
      : {}),
    ...(snapshot.reveal
      ? {
          reveal: {
            lockedResultHash: snapshot.reveal.locked_result_sha256,
            catalogSource: snapshot.reveal.catalog_source,
            catalogPayload: snapshot.reveal.catalog_payload,
            revealedAt: snapshot.reveal.revealed_at,
          },
        }
      : {}),
  }
}

function payloadString(event: InvestigationEvent, key: string): string | undefined {
  const value = event.payload[key]
  return typeof value === "string" ? value : undefined
}

function payloadAgent(event: InvestigationEvent, key = "role"): AgentId | undefined {
  const value = payloadString(event, key)
  return AGENT_DEFINITIONS.some((agent) => agent.id === value) ? value as AgentId : undefined
}

function traceForEvent(event: InvestigationEvent): PresentationEvent["trace"] {
  const role = payloadAgent(event)
  const toolName = payloadString(event, "tool_name")
  const failure = payloadString(event, "concise_reason") ?? payloadString(event, "terminal_reason")
  const headline = failure ?? payloadString(event, "status") ?? payloadString(event, "route") ?? event.type
  const tone: SemanticTone = event.type.includes("failed") || event.type === "run.failed" ? "danger" : event.type.startsWith("tool") || event.type.startsWith("evidence") ? "science" : "model"
  return {
    actor: role?.toUpperCase() ?? (toolName ? "SCIENCE TOOL" : "RUNTIME"),
    headline,
    detail: toolName ?? payloadString(event, "reason_code") ?? event.step_id,
    tone,
    evidenceRef: payloadString(event, "evidence_ref") ?? payloadString(event, "evidence_id"),
  }
}

export function presentationEventFromBackendEvent(
  event: InvestigationEvent,
  snapshot: MissionControlSnapshot,
): PresentationEvent | null {
  const base = { eventId: event.event_id, timestamp: event.timestamp, holdMs: 0, trace: traceForEvent(event) }
  const role = payloadAgent(event)
  switch (event.type) {
    case "agent.started":
      return role ? { ...base, type: "agent.started", agentId: role } : { ...base, type: "audit.event" }
    case "agent.decision":
    case "agent.completed":
    case "agent.skipped": {
      if (!role) return { ...base, type: "audit.event" }
      const checkpoint = [...snapshot.role_checkpoints].reverse().find((item) => item.role === role)
      return { ...base, type: "agent.decision", agentId: role, update: checkpoint ? checkpointAgent(checkpoint, AGENT_DEFINITIONS.find((item) => item.id === role)!) : {} }
    }
    case "agent.handoff": {
      const from = payloadAgent(event, "from_role")
      const to = payloadAgent(event, "to_role")
      return from && to ? { ...base, type: "agent.handoff", from, to, kind: "model" } : { ...base, type: "audit.event" }
    }
    case "critic.review": {
      const latest = snapshot.critic_decisions.at(-1)
      return latest ? { ...base, type: "critic.review", verdict: latest.verdict, summary: latest.concise_reason } : { ...base, type: "audit.event" }
    }
    case "tool.started": {
      const tool = snapshot.tool_executions.find((item) => item.action_id === event.action_id)
      return tool ? { ...base, type: "tool.started", tool: toolPresentation(tool), budgetUsed: snapshot.budgets.adaptive_cost_units_used } : { ...base, type: "audit.event" }
    }
    case "tool.completed":
    case "tool.failed": {
      const tool = snapshot.tool_executions.find((item) => item.action_id === event.action_id)
      return tool ? { ...base, type: "tool.completed", tool: toolPresentation(tool) } : { ...base, type: "audit.event" }
    }
    case "evidence.appended": {
      const id = payloadString(event, "evidence_id")
      const evidence = snapshot.evidence.find((item) => item.evidence_id === id)
      return evidence ? { ...base, type: "evidence.appended", evidence: evidencePresentation(evidence) } : { ...base, type: "audit.event" }
    }
    case "result.locked": {
      const hash = payloadString(event, "sha256") ?? snapshot.lock.sha256
      const lockedAt = snapshot.lock.locked_at
      return hash && lockedAt ? { ...base, type: "result.locked", hash, lockedAt } : { ...base, type: "audit.event" }
    }
    case "hypothesis.updated":
      return { ...base, type: "audit.event" }
    case "status.changed":
    case "investigation.created":
    case "director.route":
    case "agent.queued":
    case "inference.attempt":
    case "inference.fallback":
    case "inference.summary":
    case "budget.updated":
    case "model.retry":
    case "recovery.completed":
    case "catalog.revealed":
    case "run.failed":
    default:
      return { ...base, type: "audit.event" }
  }
}

export function mergeBackendEvent(
  state: InvestigationPresentationState,
  event: InvestigationEvent,
  snapshot?: MissionControlSnapshot,
): InvestigationPresentationState {
  if (!snapshot) {
    const timelineEvent: PresentationEvent = {
      eventId: event.event_id,
      timestamp: event.timestamp,
      holdMs: 0,
      trace: traceForEvent(event),
      type: "audit.event",
    }
    return applyPresentationEvent(state, timelineEvent)
  }
  const normalized = presentationEventFromBackendEvent(event, snapshot)
  return normalized ? applyPresentationEvent(state, normalized) : state
}
