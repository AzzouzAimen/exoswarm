import { describe, expect, it } from "vitest"

import { subscribeToInvestigation } from "./events"

class FakeEventSource {
  onopen: ((event: Event) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readonly listeners = new Map<string, EventListener>()
  closed = false

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener)
  }

  close() {
    this.closed = true
  }

  emit(type: string, data: unknown) {
    this.listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent<string>)
  }
}

const event = (sequence: number, eventId = `evt_${sequence}`) => ({
  event_id: eventId,
  run_id: "run_1",
  step_id: "step_1",
  action_id: "action_1",
  sequence,
  timestamp: "2026-08-16T00:00:00Z",
  type: "status.changed",
  payload: { status: "SEARCHING" },
  schema_version: "1",
})

describe("cursor-aware investigation events", () => {
  it("sends after_sequence, suppresses cursor duplicates, and closes cleanly", () => {
    const source = new FakeEventSource()
    const received: number[] = []
    const errors: Error[] = []
    const close = subscribeToInvestigation("run_1", {
      afterSequence: 3,
      onEvent: (next) => received.push(next.sequence),
      onError: (error) => errors.push(error),
      eventSourceFactory: (url) => {
        expect(url).toContain("after_sequence=3")
        return source
      },
    })

    source.emit("status.changed", event(3))
    source.emit("status.changed", event(4))
    source.emit("status.changed", event(4, "another-id"))
    source.emit("status.changed", event(5))
    expect(received).toEqual([4, 5])
    expect(errors).toHaveLength(0)
    close()
    expect(source.closed).toBe(true)
  })

  it("reports malformed envelopes without crashing the stream", () => {
    const source = new FakeEventSource()
    const errors: Error[] = []
    subscribeToInvestigation("run_1", {
      onEvent: () => undefined,
      onError: (error) => errors.push(error),
      eventSourceFactory: () => source,
    })
    source.emit("hypothesis.updated", { sequence: 1, payload: {} })
    expect(errors[0]?.message).toContain("Malformed")
  })
})
