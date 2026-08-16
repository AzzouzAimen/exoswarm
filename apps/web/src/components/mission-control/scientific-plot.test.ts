import { describe, expect, it } from "vitest"

import type { InstrumentPresentation } from "./model/presentation-state"
import { plotContentState, toPlotlyTrace } from "./scientific-plot"

const instrument = (values: Partial<InstrumentPresentation>): InstrumentPresentation => ({
  mode: "secondary",
  label: "Hidden companion check",
  available: true,
  plot: { traces: [], xLabel: "Check", yLabel: "Measured value", annotation: "No chart required" },
  readouts: [{ label: "Second dip", value: "not detected", evidenceRef: "evidence_2" }],
  ...values,
})

describe("scientific plot presentation", () => {
  it("uses categorical bar hover text without inventing day units", () => {
    const trace = toPlotlyTrace({ name: "Odd/even", x: [1, 2], y: [3, 4], kind: "bar", tone: "science" })
    const hovertemplate = "hovertemplate" in trace ? trace.hovertemplate : undefined
    expect(hovertemplate).toBe("Category %{x}<br>Value %{y}<extra></extra>")
    expect(String(hovertemplate)).not.toContain(" d")
  })

  it("distinguishes available readout-only evidence from unavailable evidence", () => {
    expect(plotContentState(instrument({}))).toBe("readouts")
    expect(plotContentState(instrument({ available: false, unavailableReason: "Not measured", readouts: [] }))).toBe("unavailable")
    expect(plotContentState(instrument({
      plot: {
        traces: [{ name: "flux", x: [1], y: [1], kind: "line", tone: "science" }],
        xLabel: "BTJD",
        yLabel: "Flux",
        annotation: "Measured",
      },
    }))).toBe("chart")
  })
})
