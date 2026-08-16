import { describe, expect, it } from "vitest"

import type { InvestigationEvent, MissionControlSnapshot } from "@/lib/contracts"

import type { InvestigationPresentationState } from "../model/presentation-state"
import {
  appendEventTail,
  canAcceptSnapshot,
  INITIAL_PLAYBACK_STATE,
  livePlaybackReducer,
  plotEvidenceVersion,
  reconcileEventTail,
  shouldRequestPlot,
} from "./live-state"

const snapshot = (lastSequence: number, runId = "run_1"): MissionControlSnapshot => ({
  run_id: runId,
  last_sequence: lastSequence,
  available_plot_modes: [],
  plot_evidence_refs: [],
  candidate_signals: [],
} as unknown as MissionControlSnapshot)

const event = (sequence: number, eventId = `evt_${sequence}`): InvestigationEvent => ({
  event_id: eventId,
  run_id: "run_1",
  step_id: "step_1",
  action_id: "action_1",
  sequence,
  timestamp: "2026-08-16T00:00:00Z",
  type: "status.changed",
  payload: {},
  schema_version: "1",
})

const presentation = (timelineIds: string[]): InvestigationPresentationState => ({
  timeline: timelineIds.map((id, index) => ({ id, sequence: index + 1 })),
} as unknown as InvestigationPresentationState)

describe("live snapshot reconciliation", () => {
  it("rejects snapshots for another run and snapshots behind the accepted cursor", () => {
    expect(canAcceptSnapshot(snapshot(8), "run_1", 9)).toBe(false)
    expect(canAcceptSnapshot(snapshot(10, "run_2"), "run_1", 9)).toBe(false)
    expect(canAcceptSnapshot(snapshot(9), "run_1", 9)).toBe(true)
  })

  it("prunes acknowledged events and deduplicates the remaining event tail", () => {
    const tail = [event(3), event(5), event(5, "duplicate_sequence"), event(6)]
    expect(reconcileEventTail(tail, snapshot(5)).map((item) => item.event_id)).toEqual(["evt_6"])
    expect(appendEventTail([event(6)], event(6, "duplicate"), 5)).toHaveLength(1)
    expect(appendEventTail([event(6)], event(5), 5)).toHaveLength(1)
  })

  it("uses snapshots as durable history and replaces the same cursor without duplicate entries", () => {
    const first = livePlaybackReducer(INITIAL_PLAYBACK_STATE, {
      type: "accept",
      snapshot: snapshot(4),
      presentation: presentation(["status-SEARCHING", "evidence-1"]),
    })
    const replaced = livePlaybackReducer(first, {
      type: "accept",
      snapshot: snapshot(4),
      presentation: presentation(["status-VETTING", "evidence-1"]),
    })
    const next = livePlaybackReducer(replaced, {
      type: "accept",
      snapshot: snapshot(5),
      presentation: presentation(["status-FINALIZING", "evidence-1"]),
    })

    expect(replaced.history).toHaveLength(1)
    expect(next.history).toHaveLength(2)
    for (const entry of next.history) {
      const ids = entry.presentation.timeline.map((item) => item.id)
      expect(new Set(ids).size).toBe(ids.length)
    }
  })
})

describe("plot evidence versions", () => {
  it("changes when durable plot evidence changes and gates raw until candidate evidence exists", () => {
    const pending = snapshot(4)
    const candidate = { ...pending, candidate_signals: [{ candidate_id: "candidate_1" }] } as MissionControlSnapshot
    const available = {
      ...candidate,
      last_sequence: 5,
      available_plot_modes: ["raw"],
      plot_evidence_refs: ["evidence_1"],
    } as MissionControlSnapshot

    expect(shouldRequestPlot(pending, "raw")).toBe(false)
    expect(shouldRequestPlot(candidate, "raw")).toBe(true)
    expect(shouldRequestPlot(pending, "secondary")).toBe(false)
    expect(plotEvidenceVersion(pending, "raw")).not.toBe(plotEvidenceVersion(available, "raw"))
  })
})
