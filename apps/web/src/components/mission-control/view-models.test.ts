import { describe, expect, it } from "vitest"

import type { MissionControlSnapshot, ViewerTarget } from "@/lib/contracts"

import { configuredDataMode } from "./runtime-mode"
import {
  launchTargets,
  liveResultComparisonView,
  targetPage,
  targetPageCount,
  targetPageForSelection,
} from "./view-models"

const viewerTarget: ViewerTarget = {
  opaque_target_id: "TARGET-X17",
  target_name: "Known planet",
  tic_id: "123456789",
  catalog_disposition: "CONFIRMED_PLANET",
  catalog_source: "Official catalog",
  catalog_source_url: "https://example.com/catalog",
  known_values: { period_days: 3.2 },
}

describe("source-neutral mission-control view models", () => {
  it("defaults to live and requires fixture mode explicitly", () => {
    expect(configuredDataMode(undefined)).toBe("live")
    expect(configuredDataMode("unexpected")).toBe("live")
    expect(configuredDataMode("fixture")).toBe("fixture")
  })

  it("joins the separate viewer identity without changing the agent-safe target contract", () => {
    expect(launchTargets([{ opaque_target_id: "TARGET-X17", cached_lightcurve_available: true, cached_tpf_available: false }], [viewerTarget])).toEqual([
      { id: "TARGET-X17", observationLabel: "Cached TESS observation", available: true, officialIdentity: "Known planet" },
    ])
  })

  it("paginates observation choices three at a time and locates the selected page", () => {
    const targets = ["A", "B", "C", "D", "E"].map((id) => ({
      id: `TARGET-${id}`,
      observationLabel: "Cached TESS observation",
      available: true,
    }))

    expect(targetPageCount(targets)).toBe(2)
    expect(targetPage(targets, 0).map((target) => target.id)).toEqual(["TARGET-A", "TARGET-B", "TARGET-C"])
    expect(targetPage(targets, 1).map((target) => target.id)).toEqual(["TARGET-D", "TARGET-E"])
    expect(targetPageForSelection(targets, "TARGET-E")).toBe(1)
  })

  it("compares a finished independent result with the viewer reference without reveal state", () => {
    const snapshot = {
      status: "READY_TO_LOCK",
      disposition: "PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING",
      terminal_reason: "complete",
      completed_tests: [],
      inference_summary: { agent_calls: 2 },
      budgets: { tool_call_count: 3 },
      run_id: "run_1",
      candidate_signals: [{ measurements: { period: { display_value: "3.19 d" } } }],
      lock: { state: "GROUND_TRUTH_LOCKED", sha256: null, locked_at: null },
      reveal: null,
    } as unknown as MissionControlSnapshot
    const view = liveResultComparisonView(snapshot, [], viewerTarget)
    expect(view.verdict).toBe("match")
    expect(view.reference.identity).toBe("Known planet")
    expect(view.comparisonRows).toContainEqual({ label: "Period days", independent: "3.19 d", official: "3.200000 d" })
  })

  it("uses an honest insufficient verdict when the run made no claim", () => {
    const ready = {
      status: "INSUFFICIENT_EVIDENCE",
      disposition: null,
      terminal_reason: "bounded checks complete",
      completed_tests: ["candidate_search"],
      inference_summary: { agent_calls: 2 },
      budgets: { tool_call_count: 3 },
      run_id: "run_ready",
      candidate_signals: [],
      lock: { state: "GROUND_TRUTH_LOCKED", sha256: null, locked_at: null },
      reveal: null,
    } as unknown as MissionControlSnapshot

    const view = liveResultComparisonView(ready, [], viewerTarget)
    expect(view.verdict).toBe("insufficient")
    expect(view.headline).toBe("The agents could not reach a supported conclusion")
    expect(view.reasons).toEqual(["Candidate search"])
  })
})
