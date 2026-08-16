import type {
  ArtifactListResponse,
  ClientErrorShape,
  CreateInvestigationResponse,
  InvestigationView,
  MissionControlSnapshot,
  PlotMode,
  PlotView,
  TargetOption,
  ViewerTarget,
} from "./contracts"

export const apiBase = process.env.NEXT_PUBLIC_EXOSWARM_API_URL ?? "http://localhost:8000"

export class ClientError extends Error implements ClientErrorShape {
  readonly code: string
  readonly run_id: string | null
  readonly recoverable: boolean
  readonly status: number

  constructor(shape: ClientErrorShape, status = 0) {
    super(shape.message)
    this.name = "ClientError"
    this.code = shape.code
    this.run_id = shape.run_id
    this.recoverable = shape.recoverable
    this.status = status
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

async function parseError(response: Response): Promise<ClientError> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = null
  }
  const payload = isRecord(body) ? body : {}
  const detail = isRecord(payload.detail) ? payload.detail : payload
  const fallback = `Request failed with status ${response.status}`
  return new ClientError(
    {
      code: typeof detail.code === "string" ? detail.code : `HTTP_${response.status}`,
      message:
        typeof detail.message === "string"
          ? detail.message
          : typeof payload.detail === "string"
            ? payload.detail
            : fallback,
      run_id: typeof detail.run_id === "string" ? detail.run_id : null,
      recoverable: typeof detail.recoverable === "boolean" ? detail.recoverable : false,
    },
    response.status,
  )
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { cache: "no-store", ...init })
  if (!response.ok) throw await parseError(response)
  return response.json() as Promise<T>
}

export function listTargets(signal?: AbortSignal): Promise<TargetOption[]> {
  return request("/api/targets", { signal })
}

export function listViewerTargets(signal?: AbortSignal): Promise<ViewerTarget[]> {
  return request("/api/viewer/targets", { signal })
}

export function createInvestigation(
  opaqueTargetId: string,
  idempotencyKey = globalThis.crypto.randomUUID(),
  signal?: AbortSignal,
): Promise<CreateInvestigationResponse> {
  return request("/api/investigations", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ opaque_target_id: opaqueTargetId }),
    signal,
  })
}

export function getInvestigation(runId: string, signal?: AbortSignal): Promise<InvestigationView> {
  return request(`/api/investigations/${encodeURIComponent(runId)}`, { signal })
}

export function getMissionControl(runId: string, signal?: AbortSignal): Promise<MissionControlSnapshot> {
  return request(`/api/investigations/${encodeURIComponent(runId)}/mission-control`, { signal })
}

export function resumeInvestigation(runId: string, signal?: AbortSignal): Promise<CreateInvestigationResponse> {
  return request(`/api/investigations/${encodeURIComponent(runId)}/resume`, { method: "POST", signal })
}

export function listArtifacts(runId: string, signal?: AbortSignal): Promise<ArtifactListResponse> {
  return request(`/api/investigations/${encodeURIComponent(runId)}/artifacts`, { signal })
}

export function getInvestigationPlot(
  runId: string,
  mode: PlotMode,
  signal?: AbortSignal,
): Promise<PlotView> {
  return request(
    `/api/investigations/${encodeURIComponent(runId)}/mission-control/plots/${encodeURIComponent(mode)}`,
    { signal },
  )
}
