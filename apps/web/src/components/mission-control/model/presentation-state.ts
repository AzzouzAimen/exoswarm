export type AgentId =
  | "director"
  | "observer"
  | "signal"
  | "transit_hunter"
  | "skeptic"
  | "critic"

export type AgentNodeId = AgentId | "science-tool" | "evidence-ledger"

export type InvestigationPhase =
  | "observing"
  | "candidate"
  | "characterizing"
  | "measuring"
  | "challenging"
  | "reviewing"
  | "testing"
  | "locking"
  | "locked"

export type CameraPose =
  | "field"
  | "candidate"
  | "transit"
  | "measurement"
  | "alternatives"
  | "lock"

export type InstrumentMode =
  | "raw"
  | "bls"
  | "phase-fold"
  | "odd-even"
  | "secondary"
  | "harmonic"

export type SemanticTone =
  | "neutral"
  | "model"
  | "science"
  | "unresolved"
  | "approved"
  | "danger"

export interface AgentPresentation {
  id: AgentId
  label: string
  function: string
  status: "waiting" | "active" | "reviewing" | "complete"
  summary: string
  inspector: {
    currentQuestion: string
    evidenceRefs: string[]
    action: string
    expectedDiscriminator: string
    model: string
    latency: string
    schema: "pending" | "valid" | "scripted"
  }
}

export interface EvidencePresentation {
  id: string
  kind: string
  sourceTool: string
  summary: string
  measurement?: {
    value: number
    displayValue: string
    unit: string
  }
  supports: string[]
  contradicts: string[]
  provenance: string
}

export interface HypothesisPresentation {
  id: string
  label: string
  state: "unresolved" | "supported" | "under-test" | "weakened"
  evidenceRefs: string[]
  note: string
}

export interface PlotTracePresentation {
  name: string
  x: number[]
  y: number[]
  kind: "line" | "markers" | "bar"
  tone: "science" | "muted" | "unresolved" | "approved"
  dash?: "solid" | "dot" | "dash"
}

export interface PlotPresentation {
  traces: PlotTracePresentation[]
  xLabel: string
  yLabel: string
  annotation: string
}

export interface InstrumentPresentation {
  mode: InstrumentMode
  label: string
  plot: PlotPresentation
  readouts: Array<{
    label: string
    value: string
    evidenceRef?: string
  }>
}

export interface ToolPresentation {
  name: string
  status: "idle" | "running" | "complete" | "failed"
  durationMs?: number
  evidenceRef?: string
  authority: "deterministic"
}

export interface TimelineRecord {
  id: string
  sequence: number
  timestamp: string
  eventType: PresentationEventType
  agentId?: AgentId
  tool?: ToolPresentation
  handoff?: {
    from: AgentNodeId
    to: AgentNodeId
    kind: "model" | "science"
  }
  actor: string
  headline: string
  detail: string
  tone: SemanticTone
  evidenceRef?: string
}

export type PresentationEventType =
  | "agent.started"
  | "agent.decision"
  | "agent.handoff"
  | "critic.review"
  | "tool.started"
  | "tool.completed"
  | "evidence.appended"
  | "hypothesis.updated"
  | "result.locked"

export interface InvestigationPresentationState {
  run: {
    id: string
    mode: "demo"
  }
  target: {
    id: string
    sector: string
    dataLabel: string
    groundTruthState: "sealed" | "revealed"
  }
  phase: InvestigationPhase
  stageIndex: number
  stageLabel: string
  currentQuestion: string
  activeAgentId?: AgentId
  agents: AgentPresentation[]
  activeHandoff?: {
    from: AgentNodeId
    to: AgentNodeId
    kind: "model" | "science"
  }
  hypotheses: HypothesisPresentation[]
  evidence: EvidencePresentation[]
  activeTool?: ToolPresentation
  instrument: InstrumentPresentation
  evidenceBudget: {
    used: number
    total: number
  }
  cameraPose: CameraPose
  timeline: TimelineRecord[]
  lock?: {
    hash: string
    lockedAt: string
  }
}

interface EventBase {
  eventId: string
  timestamp: string
  holdMs: number
  trace: Omit<
    TimelineRecord,
    "id" | "sequence" | "timestamp" | "eventType" | "agentId" | "tool" | "handoff"
  >
  view?: Partial<
    Pick<
      InvestigationPresentationState,
      | "phase"
      | "stageIndex"
      | "stageLabel"
      | "currentQuestion"
      | "cameraPose"
      | "instrument"
    >
  >
}

export type PresentationEvent = EventBase &
  (
    | { type: "agent.started"; agentId: AgentId }
    | {
        type: "agent.decision"
        agentId: AgentId
        update: Partial<AgentPresentation>
      }
    | {
        type: "agent.handoff"
        from: AgentNodeId
        to: AgentNodeId
        kind: "model" | "science"
      }
    | {
        type: "critic.review"
        verdict: "APPROVE" | "REVISE" | "VETO"
        summary: string
      }
    | { type: "tool.started"; tool: ToolPresentation; budgetUsed: number }
    | { type: "tool.completed"; tool: ToolPresentation }
    | { type: "evidence.appended"; evidence: EvidencePresentation }
    | {
        type: "hypothesis.updated"
        hypothesisId: string
        update: Partial<HypothesisPresentation>
      }
    | { type: "result.locked"; hash: string; lockedAt: string }
  )
