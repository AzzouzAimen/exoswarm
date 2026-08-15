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
    "agent.decision",
    "critic.review",
    "tool.completed",
    "tool.failed",
    "evidence.appended",
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

