import { describe, expect, it, vi } from "vitest"

import {
  clearTraceRevealTimer,
  createTraceRevealQueue,
  reconcileTraceRevealQueue,
  revealAllTraceRecords,
  revealNextTraceRecord,
  TRACE_REVEAL_INTERVAL_MS,
} from "./trace-pacing"
import type { TimelineRecord } from "./presentation-state"

function record(id: string, headline = id): TimelineRecord {
  return {
    id,
    sequence: 1,
    timestamp: "2026-08-16T00:00:00Z",
    eventType: "audit.event",
    boundary: "authority",
    actor: "RUNTIME",
    headline,
    detail: id,
    tone: "neutral",
  }
}

describe("investigation trace pacing", () => {
  it("reveals only one queued step per 300 ms interval", () => {
    expect(TRACE_REVEAL_INTERVAL_MS).toBe(300)
    const queue = createTraceRevealQueue([record("one"), record("two"), record("three")])
    const advanced = revealNextTraceRecord(queue)

    expect(advanced.visible.map((item) => item.id)).toEqual(["one"])
    expect(advanced.pending.map((item) => item.id)).toEqual(["two", "three"])
  })

  it("keeps first-seen order when a live snapshot replaces and reorders its timeline", () => {
    const initial = createTraceRevealQueue([record("status-searching"), record("tool-1")])
    const afterFirstReveal = revealNextTraceRecord(initial)
    const reconciled = reconcileTraceRevealQueue(afterFirstReveal, [
      record("status-vetting"),
      record("tool-1", "Tool result updated"),
      record("agent-observer"),
    ])

    expect(reconciled.visible.map((item) => item.id)).toEqual(["status-searching"])
    expect(reconciled.pending.map((item) => item.id)).toEqual([
      "tool-1",
      "status-vetting",
      "agent-observer",
    ])
    expect(reconciled.pending[0]?.headline).toBe("Tool result updated")
  })

  it("does not flush visible work when a rebuilt live timeline becomes shorter", () => {
    const queue = {
      visible: [record("one")],
      pending: [record("two"), record("three")],
    }
    const reconciled = reconcileTraceRevealQueue(queue, [record("three")])

    expect(reconciled.visible.map((item) => item.id)).toEqual(["one"])
    expect(reconciled.pending.map((item) => item.id)).toEqual(["two", "three"])
  })

  it("reveals every queued record immediately for reduced motion", () => {
    const revealed = revealAllTraceRecords(
      createTraceRevealQueue([record("one"), record("two")]),
    )

    expect(revealed.visible.map((item) => item.id)).toEqual(["one", "two"])
    expect(revealed.pending).toEqual([])
  })

  it("clears the timer identity when React cleans up the pacing effect", () => {
    const clearInterval = vi.fn()

    expect(clearTraceRevealTimer(42, clearInterval)).toBeUndefined()
    expect(clearInterval).toHaveBeenCalledOnce()
    expect(clearInterval).toHaveBeenCalledWith(42)
  })
})
