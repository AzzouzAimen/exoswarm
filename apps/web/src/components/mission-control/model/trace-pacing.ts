export const TRACE_REVEAL_INTERVAL_MS = 300

export function nextTraceRevealCount(currentCount: number, availableCount: number) {
  const current = Math.max(0, currentCount)
  const available = Math.max(0, availableCount)
  return Math.min(current + 1, available)
}
