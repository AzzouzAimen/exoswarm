import type { TimelineRecord } from "./presentation-state"

export const TRACE_REVEAL_INTERVAL_MS = 300

export function traceAutoScrollBehavior(shouldReduceMotion: boolean | null) {
  return shouldReduceMotion ? "auto" as const : "smooth" as const
}

export interface TraceRevealQueue {
  visible: TimelineRecord[]
  pending: TimelineRecord[]
}

export function clearTraceRevealTimer(
  timerId: number | undefined,
  clearInterval: (timerId: number) => void,
) {
  if (timerId !== undefined) clearInterval(timerId)
  return undefined
}

export function createTraceRevealQueue(
  records: TimelineRecord[],
  revealImmediately = false,
): TraceRevealQueue {
  return revealImmediately
    ? { visible: records, pending: [] }
    : { visible: [], pending: records }
}

export function reconcileTraceRevealQueue(
  queue: TraceRevealQueue,
  incoming: TimelineRecord[],
): TraceRevealQueue {
  const incomingById = new Map(incoming.map((record) => [record.id, record]))
  const knownIds = new Set([
    ...queue.visible.map((record) => record.id),
    ...queue.pending.map((record) => record.id),
  ])
  const additions = incoming.filter((record) => !knownIds.has(record.id))

  return {
    visible: queue.visible.map((record) => incomingById.get(record.id) ?? record),
    pending: [
      ...queue.pending.map((record) => incomingById.get(record.id) ?? record),
      ...additions,
    ],
  }
}

export function revealNextTraceRecord(queue: TraceRevealQueue): TraceRevealQueue {
  const [nextRecord, ...remaining] = queue.pending
  if (!nextRecord) return queue
  return {
    visible: [...queue.visible, nextRecord],
    pending: remaining,
  }
}

export function revealAllTraceRecords(queue: TraceRevealQueue): TraceRevealQueue {
  if (!queue.pending.length) return queue
  return {
    visible: [...queue.visible, ...queue.pending],
    pending: [],
  }
}
