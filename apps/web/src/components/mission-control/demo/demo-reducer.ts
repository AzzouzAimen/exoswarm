import type {
  AgentId,
  AgentPresentation,
  InvestigationPresentationState,
  PresentationEvent,
} from "../model/presentation-state"

function updateAgent(
  agents: AgentPresentation[],
  agentId: AgentId,
  update: Partial<AgentPresentation>,
) {
  return agents.map((agent) => (agent.id === agentId ? { ...agent, ...update } : agent))
}

export function applyPresentationEvent(
  state: InvestigationPresentationState,
  event: PresentationEvent,
): InvestigationPresentationState {
  const next: InvestigationPresentationState = {
    ...state,
    ...event.view,
    activeHandoff: undefined,
    timeline: [
      ...state.timeline,
      {
        ...event.trace,
        id: event.eventId,
        sequence: state.timeline.length + 1,
        timestamp: event.timestamp,
      },
    ],
  }

  switch (event.type) {
    case "agent.started": {
      const agents = state.agents.map((agent) => ({
        ...agent,
        status:
          agent.id === event.agentId
            ? "active" as const
            : agent.status === "active" || agent.status === "reviewing"
              ? "complete" as const
              : agent.status,
      }))
      return { ...next, agents, activeAgentId: event.agentId }
    }
    case "agent.decision":
      return { ...next, agents: updateAgent(state.agents, event.agentId, event.update) }
    case "agent.handoff": {
      let agents = state.agents
      if (event.from !== "science-tool" && event.from !== "evidence-ledger") {
        agents = updateAgent(agents, event.from, { status: "complete" })
      }
      if (event.to !== "science-tool" && event.to !== "evidence-ledger") {
        agents = updateAgent(agents, event.to, { status: "reviewing" })
      }
      return {
        ...next,
        agents,
        activeAgentId:
          event.to === "science-tool" || event.to === "evidence-ledger" ? undefined : event.to,
        activeHandoff: { from: event.from, to: event.to, kind: event.kind },
      }
    }
    case "critic.review":
      return {
        ...next,
        agents: updateAgent(state.agents, "critic", {
          status: "complete",
          summary: `${event.verdict} · ${event.summary}`,
          inspector: {
            currentQuestion: "Does harmonic_test discriminate the strongest unresolved alternative?",
            evidenceRefs: ["E14", "E17"],
            action: "harmonic_test",
            expectedDiscriminator: "P/2, P and 2P consistency",
            model: "DeepSeek-V4 · demo trace",
            latency: "2.1 s · synthetic telemetry",
            schema: "valid",
          },
        }),
      }
    case "tool.started":
      return {
        ...next,
        activeAgentId: undefined,
        activeTool: event.tool,
        evidenceBudget: { ...state.evidenceBudget, used: event.budgetUsed },
      }
    case "tool.completed":
      return { ...next, activeTool: event.tool }
    case "evidence.appended":
      return {
        ...next,
        evidence: state.evidence.some((item) => item.id === event.evidence.id)
          ? state.evidence
          : [...state.evidence, event.evidence],
      }
    case "hypothesis.updated":
      return {
        ...next,
        hypotheses: state.hypotheses.map((hypothesis) =>
          hypothesis.id === event.hypothesisId
            ? { ...hypothesis, ...event.update }
            : hypothesis,
        ),
      }
    case "result.locked":
      return {
        ...next,
        activeAgentId: undefined,
        activeHandoff: undefined,
        agents: state.agents.map((agent) => ({ ...agent, status: "complete" })),
        lock: { hash: event.hash, lockedAt: event.lockedAt },
      }
  }
}

export function replayPresentation(
  initialState: InvestigationPresentationState,
  events: PresentationEvent[],
  step: number,
) {
  return events.slice(0, step).reduce(applyPresentationEvent, initialState)
}
