import { describe, expect, it } from "vitest"

import { DEMO_EVENTS, DEMO_INITIAL_STATE } from "./demo-investigation.fixture"
import { replayPresentation } from "./demo-reducer"

describe("demo presentation replay", () => {
  it("starts without inferred candidate geometry or a result lock", () => {
    const state = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 0)

    expect(state.phase).toBe("observing")
    expect(state.cameraPose).toBe("field")
    expect(state.evidence.map((item) => item.id)).toEqual(["E11"])
    expect(state.lock).toBeUndefined()
    expect(state.target.groundTruthState).toBe("sealed")
  })

  it("introduces candidate geometry only after the deterministic period search", () => {
    const beforeSearchCompletes = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 2)
    const afterSearchCompletes = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 3)

    expect(beforeSearchCompletes.phase).toBe("observing")
    expect(afterSearchCompletes.phase).toBe("candidate")
    expect(afterSearchCompletes.instrument.mode).toBe("bls")
  })

  it("appends evidence once and reconstructs a selected step deterministically", () => {
    const firstReplay = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 17)
    const secondReplay = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, 17)

    expect(firstReplay).toEqual(secondReplay)
    expect(firstReplay.evidence.map((item) => item.id)).toEqual(["E11", "E14", "E17", "E18"])
    expect(new Set(firstReplay.evidence.map((item) => item.id)).size).toBe(4)
    expect(firstReplay.timeline).toHaveLength(17)
  })

  it("locks measurements while keeping catalog ground truth sealed", () => {
    const state = replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, DEMO_EVENTS.length)

    expect(state.phase).toBe("locked")
    expect(state.lock?.hash).toMatch(/^[0-9a-f]{64}$/)
    expect(state.target.groundTruthState).toBe("sealed")
    expect(state.activeHandoff).toBeUndefined()
    expect(state.agents.every((agent) => agent.status === "complete")).toBe(true)
  })
})
