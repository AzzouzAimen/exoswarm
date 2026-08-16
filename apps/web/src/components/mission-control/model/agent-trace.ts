import type {
  AgentId,
  AgentPresentation,
  InvestigationPresentationState,
  TimelineRecord,
} from "./presentation-state"

export interface AgentTraceStage {
  id: string
  agent: AgentPresentation
  records: TimelineRecord[]
  status: "active" | "complete"
}

function isAgentNode(value: string): value is AgentId {
  return [
    "director",
    "observer",
    "signal",
    "transit_hunter",
    "skeptic",
    "critic",
  ].includes(value)
}

function recordAgentId(record: TimelineRecord, currentAgentId?: AgentId) {
  if (record.agentId) return record.agentId
  if (record.handoff && isAgentNode(record.handoff.to)) return record.handoff.to
  return currentAgentId
}

export function buildAgentTraceStages(
  state: Pick<
    InvestigationPresentationState,
    "timeline" | "agents" | "activeAgentId" | "activeTool" | "activeHandoff" | "phase"
  >,
): AgentTraceStage[] {
  const stages: Array<Omit<AgentTraceStage, "status">> = []
  const agentOccurrences = new Map<AgentId, number>()
  let currentAgentId: AgentId | undefined

  for (const record of state.timeline) {
    const nextAgentId = recordAgentId(record, currentAgentId)
    if (!nextAgentId) continue

    const startsNewStage =
      nextAgentId !== currentAgentId ||
      record.eventType === "agent.started" ||
      (record.eventType === "agent.handoff" && record.handoff?.to === nextAgentId)

    if (startsNewStage) {
      const agent = state.agents.find((candidate) => candidate.id === nextAgentId)
      if (!agent) continue
      const occurrence = (agentOccurrences.get(nextAgentId) ?? 0) + 1
      agentOccurrences.set(nextAgentId, occurrence)
      stages.push({ id: `${nextAgentId}-${occurrence}`, agent, records: [] })
    }

    stages.at(-1)?.records.push(record)
    currentAgentId = nextAgentId
  }

  const toolIsRunning = state.activeTool?.status === "running"
  const latestStageId = stages.at(-1)?.id

  return stages.map((stage) => ({
    ...stage,
    status:
      state.phase !== "locked" &&
      stage.id === latestStageId &&
      (stage.agent.id === state.activeAgentId ||
        stage.agent.status === "active" ||
        stage.agent.status === "reviewing" ||
        state.activeHandoff?.from === stage.agent.id ||
        toolIsRunning)
        ? "active"
        : "complete",
  }))
}
