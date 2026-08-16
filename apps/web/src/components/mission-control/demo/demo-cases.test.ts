import { describe, expect, it } from "vitest"

import { DEMO_CASE_LIST } from "./demo-cases"
import { replayPresentation } from "./demo-reducer"

describe("demo case trajectories", () => {
  it.each(DEMO_CASE_LIST)("replays $id deterministically", (demoCase) => {
    const first = replayPresentation(
      demoCase.initialState,
      demoCase.events,
      demoCase.events.length,
    )
    const second = replayPresentation(
      demoCase.initialState,
      demoCase.events,
      demoCase.events.length,
    )

    expect(first).toEqual(second)
    expect(first.target.id).toBe(demoCase.id)
    expect(first.target.groundTruthState).toBe("sealed")
    expect(first.timeline).toHaveLength(demoCase.events.length)
    expect(first.timeline.every((record) => Boolean(record.boundary))).toBe(true)
  })

  it("locks both classifications but permits an inconclusive run without a lock", () => {
    const terminalStates = Object.fromEntries(
      DEMO_CASE_LIST.map((demoCase) => [
        demoCase.id,
        replayPresentation(demoCase.initialState, demoCase.events, demoCase.events.length),
      ]),
    )

    expect(terminalStates["TARGET-C11"].lock).toBeDefined()
    expect(terminalStates["TARGET-B42"].lock).toBeDefined()
    expect(terminalStates["TARGET-D31"].lock).toBeUndefined()
    expect(terminalStates["TARGET-D31"].timeline.at(-1)?.eventType).toBe("run.concluded")
  })

  it("keeps target identity out of all agent-visible state and event copy", () => {
    for (const demoCase of DEMO_CASE_LIST) {
      const agentVisibleFixture = JSON.stringify({
        state: demoCase.initialState,
        events: demoCase.events,
      })

      expect(agentVisibleFixture).not.toContain(demoCase.reveal?.targetName ?? "__no_reveal__")
      expect(agentVisibleFixture).not.toContain(demoCase.reveal?.catalogId ?? "__no_catalog__")
    }
  })
})
