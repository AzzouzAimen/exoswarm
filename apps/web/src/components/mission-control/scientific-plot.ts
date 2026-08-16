import type { Data } from "plotly.js"

import type { InstrumentPresentation, PlotTracePresentation } from "./model/presentation-state"

const TRACE_COLORS: Record<PlotTracePresentation["tone"], string> = {
  science: "#65dce4",
  muted: "#8ca3a8",
  unresolved: "#eeb862",
  approved: "#72cc9b",
}

export type PlotContentState = "chart" | "readouts" | "unavailable"

export function plotContentState(instrument: InstrumentPresentation): PlotContentState {
  if (!instrument.available) return "unavailable"
  return instrument.plot.traces.length > 0 ? "chart" : "readouts"
}

export function toPlotlyTrace(trace: PlotTracePresentation): Data {
  const color = TRACE_COLORS[trace.tone]
  if (trace.kind === "bar") {
    return {
      type: "bar",
      name: trace.name,
      x: trace.x,
      y: trace.y,
      marker: { color, line: { color: "#b6f0f2", width: 0.5 } },
      hovertemplate: "Category %{x}<br>Value %{y}<extra></extra>",
    }
  }
  return {
    type: "scatter",
    mode: trace.kind === "markers" ? "markers" : "lines",
    name: trace.name,
    x: trace.x,
    y: trace.y,
    line: { color, width: 1.35, dash: trace.dash ?? "solid" },
    marker: { color, size: trace.kind === "markers" ? 3.2 : 0, opacity: 0.72 },
    hovertemplate: "%{x:.4f}<br>%{y:.6f}<extra></extra>",
  }
}
