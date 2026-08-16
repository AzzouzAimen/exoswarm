import { apiBase } from "./api"
import { INVESTIGATION_EVENT_TYPES, type InvestigationEvent } from "./contracts"

export interface EventSourceLike {
  onopen: ((event: Event) => void) | null
  onerror: ((event: Event) => void) | null
  addEventListener(type: string, listener: EventListener): void
  close(): void
}

export type EventSourceFactory = (url: string) => EventSourceLike

export interface InvestigationSubscriptionOptions {
  afterSequence?: number
  onEvent: (event: InvestigationEvent) => void
  onOpen?: () => void
  onError?: (error: Error) => void
  onClose?: () => void
  eventSourceFactory?: EventSourceFactory
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

export function parseInvestigationEvent(value: unknown): InvestigationEvent | null {
  if (!isRecord(value) || !isRecord(value.payload)) return null
  if (
    typeof value.event_id !== "string" ||
    typeof value.run_id !== "string" ||
    typeof value.step_id !== "string" ||
    typeof value.action_id !== "string" ||
    typeof value.sequence !== "number" ||
    !Number.isInteger(value.sequence) ||
    value.sequence < 1 ||
    typeof value.timestamp !== "string" ||
    typeof value.type !== "string" ||
    value.schema_version !== "1"
  ) return null
  return value as unknown as InvestigationEvent
}

export function subscribeToInvestigation(
  runId: string,
  options: InvestigationSubscriptionOptions,
): () => void {
  const afterSequence = Math.max(0, options.afterSequence ?? 0)
  const url = new URL(`${apiBase}/api/investigations/${encodeURIComponent(runId)}/events`)
  url.searchParams.set("after_sequence", String(afterSequence))
  const factory = options.eventSourceFactory ?? ((sourceUrl) => new EventSource(sourceUrl))
  const source = factory(url.toString())
  const eventIds = new Set<string>()
  const sequences = new Set<number>()
  let closed = false

  const accept = (message: Event) => {
    try {
      const raw = JSON.parse((message as MessageEvent<string>).data) as unknown
      const event = parseInvestigationEvent(raw)
      if (!event) throw new Error("Malformed investigation event envelope")
      if (event.run_id !== runId) throw new Error("Investigation event run ID mismatch")
      if (event.sequence <= afterSequence || eventIds.has(event.event_id) || sequences.has(event.sequence)) return
      eventIds.add(event.event_id)
      sequences.add(event.sequence)
      options.onEvent(event)
    } catch (error) {
      options.onError?.(error instanceof Error ? error : new Error("Malformed investigation event"))
    }
  }

  source.onopen = () => options.onOpen?.()
  source.onerror = () => options.onError?.(new Error("Investigation event stream disconnected"))
  for (const type of INVESTIGATION_EVENT_TYPES) source.addEventListener(type, accept)

  return () => {
    if (closed) return
    closed = true
    source.close()
    options.onClose?.()
  }
}
