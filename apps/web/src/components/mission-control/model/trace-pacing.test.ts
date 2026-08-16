import { describe, expect, it } from "vitest"

import {
  nextTraceRevealCount,
  TRACE_REVEAL_INTERVAL_MS,
} from "./trace-pacing"

describe("investigation trace pacing", () => {
  it("reveals only one queued step per 300 ms interval", () => {
    expect(TRACE_REVEAL_INTERVAL_MS).toBe(300)
    expect(nextTraceRevealCount(2, 5)).toBe(3)
  })

  it("does not advance past the available trace", () => {
    expect(nextTraceRevealCount(5, 5)).toBe(5)
    expect(nextTraceRevealCount(3, 0)).toBe(0)
  })
})
