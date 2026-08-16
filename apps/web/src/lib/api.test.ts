import { afterEach, describe, expect, it, vi } from "vitest"

import { ClientError, createInvestigation, getInvestigationPlot, listTargets, listViewerTargets } from "./api"

afterEach(() => vi.restoreAllMocks())

describe("mission-control REST transport", () => {
  it("lists targets with no-store and forwards abort signals", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ opaque_target_id: "TARGET-X17", cached_lightcurve_available: true, cached_tpf_available: false }]), { status: 200 }),
    )
    const controller = new AbortController()
    await listTargets(controller.signal)
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/targets",
      expect.objectContaining({ cache: "no-store", signal: controller.signal }),
    )
  })

  it("loads the separate viewer catalog projection", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ opaque_target_id: "TARGET-X17", target_name: "Known planet" }]), { status: 200 }),
    )
    await listViewerTargets()
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/viewer/targets",
      expect.objectContaining({ cache: "no-store" }),
    )
  })

  it("preserves a caller idempotency key for create", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ run_id: "run_1" }), { status: 202 }),
    )
    await createInvestigation("TARGET-X17", "same-start-key")
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "Idempotency-Key": "same-start-key" }),
      cache: "no-store",
    }))
  })

  it("exposes the backend error contract without retrying", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "RESULT_NOT_LOCKED", message: "lock first", run_id: "run_1", recoverable: true }), { status: 403 }),
    )
    await expect(getInvestigationPlot("run_1", "raw")).rejects.toMatchObject({
      code: "RESULT_NOT_LOCKED",
      message: "lock first",
      run_id: "run_1",
      recoverable: true,
      status: 403,
    } satisfies Partial<ClientError>)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
