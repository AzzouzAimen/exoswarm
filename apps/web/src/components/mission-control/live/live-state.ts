import type { InvestigationEvent, MissionControlSnapshot, PlotMode } from "@/lib/contracts"

import type { InvestigationPresentationState } from "../model/presentation-state"

export const MAX_LIVE_HISTORY = 200

export interface DurableHistoryEntry {
  cursor: number
  presentation: InvestigationPresentationState
}

export interface LivePlaybackState {
  snapshot?: MissionControlSnapshot
  history: DurableHistoryEntry[]
  step: number
  following: boolean
}

export type LivePlaybackAction =
  | { type: "accept"; snapshot: MissionControlSnapshot; presentation: InvestigationPresentationState }
  | { type: "reset" }
  | { type: "step"; step: number }
  | { type: "following"; following: boolean }
  | { type: "replay" }

export const INITIAL_PLAYBACK_STATE: LivePlaybackState = {
  history: [],
  step: 0,
  following: true,
}

export function canAcceptSnapshot(
  snapshot: MissionControlSnapshot,
  activeRunId: string,
  acceptedSequence: number,
): boolean {
  return snapshot.run_id === activeRunId && snapshot.last_sequence >= acceptedSequence
}

export function reconcileEventTail(
  events: InvestigationEvent[],
  snapshot: MissionControlSnapshot,
): InvestigationEvent[] {
  const ids = new Set<string>()
  const sequences = new Set<number>()
  return events
    .filter((event) => event.run_id === snapshot.run_id && event.sequence > snapshot.last_sequence)
    .sort((left, right) => left.sequence - right.sequence)
    .filter((event) => {
      if (ids.has(event.event_id) || sequences.has(event.sequence)) return false
      ids.add(event.event_id)
      sequences.add(event.sequence)
      return true
    })
}

export function appendEventTail(
  events: InvestigationEvent[],
  event: InvestigationEvent,
  acceptedSequence: number,
): InvestigationEvent[] {
  if (event.sequence <= acceptedSequence) return events
  if (events.some((item) => item.event_id === event.event_id || item.sequence === event.sequence)) return events
  return [...events, event].sort((left, right) => left.sequence - right.sequence)
}

export function livePlaybackReducer(state: LivePlaybackState, action: LivePlaybackAction): LivePlaybackState {
  switch (action.type) {
    case "accept": {
      const entry = { cursor: action.snapshot.last_sequence, presentation: action.presentation }
      const last = state.history.at(-1)
      const unbounded = last?.cursor === entry.cursor
        ? [...state.history.slice(0, -1), entry]
        : [...state.history, entry]
      const dropped = Math.max(0, unbounded.length - MAX_LIVE_HISTORY)
      const history = unbounded.slice(dropped)
      return {
        snapshot: action.snapshot,
        history,
        following: state.following,
        step: state.following ? history.length - 1 : Math.max(0, state.step - dropped),
      }
    }
    case "step": {
      const step = Math.max(0, Math.min(action.step, Math.max(0, state.history.length - 1)))
      return { ...state, step, following: step === state.history.length - 1 }
    }
    case "following":
      return {
        ...state,
        following: action.following,
        step: action.following ? Math.max(0, state.history.length - 1) : state.step,
      }
    case "replay":
      return { ...state, following: false, step: 0 }
    case "reset":
      return INITIAL_PLAYBACK_STATE
  }
}

export function plotEvidenceVersion(snapshot: MissionControlSnapshot, mode: PlotMode): string {
  const evidence = [...snapshot.plot_evidence_refs].sort().join(",") || "none"
  const candidates = snapshot.candidate_signals.map((candidate) => candidate.candidate_id).sort().join(",") || "none"
  const availability = snapshot.available_plot_modes.includes(mode) ? "available" : "pending"
  return `${snapshot.run_id}:${mode}:${availability}:${candidates}:${evidence}`
}

export function shouldRequestPlot(snapshot: MissionControlSnapshot, mode: PlotMode): boolean {
  if (snapshot.available_plot_modes.includes(mode)) return true
  return mode === "raw" && snapshot.candidate_signals.length > 0
}
