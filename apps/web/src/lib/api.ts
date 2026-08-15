import type { InvestigationView } from "./contracts";

const apiBase = process.env.NEXT_PUBLIC_EXOSWARM_API_URL ?? "http://localhost:8000";

export async function getInvestigation(runId: string): Promise<InvestigationView> {
  const response = await fetch(`${apiBase}/api/investigations/${runId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Investigation request failed with status ${response.status}`);
  }
  return response.json() as Promise<InvestigationView>;
}

export async function createInvestigation(opaqueTargetId: string) {
  const idempotencyKey = globalThis.crypto.randomUUID();
  const response = await fetch(`${apiBase}/api/investigations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({ opaque_target_id: opaqueTargetId }),
  });
  if (!response.ok) {
    throw new Error(`Investigation creation failed with status ${response.status}`);
  }
  return response.json() as Promise<{
    run_id: string;
    opaque_target_id: string;
    status: string;
    lock_state: string;
    event_stream_url: string;
    execution: {
      run_id: string;
      status: "PAUSED" | "RUNNING" | "STOPPED" | "FAILED";
      active: boolean;
      advances: number;
      stop_reason: string | null;
      started_at: string | null;
      finished_at: string | null;
    };
  }>;
}
