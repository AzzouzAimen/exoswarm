import type { InvestigationEvent } from "./contracts";

const apiBase = process.env.NEXT_PUBLIC_EXOSWARM_API_URL ?? "http://localhost:8000";

export function subscribeToInvestigation(
  runId: string,
  onEvent: (event: InvestigationEvent) => void,
): () => void {
  const source = new EventSource(`${apiBase}/api/investigations/${runId}/events`);
  source.onmessage = (message) => onEvent(JSON.parse(message.data) as InvestigationEvent);
  const eventTypes = [
    "investigation.created",
    "status.changed",
    "agent.started",
    "agent.decision",
    "inference.attempt",
    "inference.fallback",
    "inference.summary",
    "critic.review",
    "tool.started",
    "tool.completed",
    "tool.failed",
    "evidence.appended",
    "budget.updated",
    "model.retry",
    "recovery.completed",
    "result.locked",
    "catalog.revealed",
    "run.failed",
  ];
  for (const type of eventTypes) {
    source.addEventListener(type, (message) => {
      onEvent(JSON.parse((message as MessageEvent<string>).data) as InvestigationEvent);
    });
  }
  return () => source.close();
}
