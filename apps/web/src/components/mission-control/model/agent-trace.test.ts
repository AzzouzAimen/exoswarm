import { describe, expect, it } from "vitest"

import { DEMO_EVENTS, DEMO_INITIAL_STATE } from "../demo/demo-investigation.fixture"
import { replayPresentation } from "../demo/demo-reducer"
import { buildAgentTraceStages } from "./agent-trace"

describe("agent trace grouping", () => {
  it("keeps deterministic work and evidence under the agent that initiated it", () => {
    const state = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 5)
    const stages = buildAgentTraceStages(state)

    expect(stages).toHaveLength(1)
    expect(stages[0].agent.id).toBe("signal")
    expect(stages[0].records.map((record) => record.eventType)).toEqual([
      "agent.started",
      "tool.started",
      "tool.completed",
      "evidence.appended",
      "hypothesis.updated",
    ])
    expect(stages[0].records[1].tool?.name).toBe("search_bls")
  })

  it("starts a new collapsible stage when work is handed to another agent", () => {
    const state = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 13)
    const stages = buildAgentTraceStages(state)

    expect(stages.map((stage) => stage.agent.id)).toEqual([
      "signal",
      "transit_hunter",
      "skeptic",
      "critic",
    ])
    expect(stages.at(-1)?.records.map((record) => record.eventType)).toEqual([
      "agent.handoff",
      "critic.review",
    ])
  })

  it("marks the responsible stage active while its deterministic tool runs", () => {
    const state = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 15)
    const stages = buildAgentTraceStages(state)

    expect(stages.at(-1)?.agent.id).toBe("critic")
    expect(stages.at(-1)?.status).toBe("active")
    expect(stages.at(-1)?.records.at(-1)?.tool).toMatchObject({
      name: "harmonic_test",
      status: "running",
    })
  })

  it("preserves the complete audit trail after the result locks", () => {
    const state = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, DEMO_EVENTS.length)
    const stages = buildAgentTraceStages(state)

    expect(stages.map((stage) => stage.agent.id)).toEqual([
      "signal",
      "transit_hunter",
      "skeptic",
      "critic",
      "director",
    ])
    expect(stages.at(-1)?.records.at(-1)?.eventType).toBe("result.locked")
    expect(stages.every((stage) => stage.status === "complete")).toBe(true)
  })
})
