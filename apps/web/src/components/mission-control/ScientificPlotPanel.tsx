"use client"

import dynamic from "next/dynamic"
import type { Data, Layout } from "plotly.js"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

import type {
  InstrumentMode,
  InstrumentPresentation,
  InvestigationPhase,
  PlotTracePresentation,
} from "./model/presentation-state"

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false })

const MODES: Array<{ id: InstrumentMode; label: string }> = [
  { id: "raw", label: "Brightness" },
  { id: "bls", label: "Period" },
  { id: "phase-fold", label: "Aligned" },
  { id: "odd-even", label: "Odd / even" },
  { id: "secondary", label: "Companion" },
  { id: "harmonic", label: "Alt periods" },
]

const TRACE_COLORS: Record<PlotTracePresentation["tone"], string> = {
  science: "#65dce4",
  muted: "#8ca3a8",
  unresolved: "#eeb862",
  approved: "#72cc9b",
}

function toPlotlyTrace(trace: PlotTracePresentation): Data {
  const color = TRACE_COLORS[trace.tone]
  if (trace.kind === "bar") {
    return {
      type: "bar",
      name: trace.name,
      x: trace.x,
      y: trace.y,
      marker: { color, line: { color: "#b6f0f2", width: 0.5 } },
      hovertemplate: "%{x:.3f} d · %{y:.2f}<extra></extra>",
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

function plotLayout(instrument: InstrumentPresentation): Partial<Layout> {
  return {
    autosize: true,
    height: 148,
    margin: { l: 54, r: 20, t: 12, b: 42 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#8ca3a8", family: "IBM Plex Mono, monospace", size: 11 },
    showlegend: instrument.plot.traces.length > 1,
    legend: { orientation: "h", x: 0, y: 1.08, font: { size: 10 } },
    hovermode: "closest",
    bargap: 0.58,
    xaxis: {
      title: { text: instrument.plot.xLabel, font: { size: 11, color: "#71868b" } },
      color: "#71868b",
      gridcolor: "rgba(117, 149, 154, 0.09)",
      zerolinecolor: "rgba(101, 220, 228, 0.16)",
      fixedrange: false,
    },
    yaxis: {
      title: { text: instrument.plot.yLabel, font: { size: 11, color: "#71868b" } },
      color: "#71868b",
      gridcolor: "rgba(117, 149, 154, 0.09)",
      zerolinecolor: "rgba(101, 220, 228, 0.16)",
      fixedrange: false,
    },
    uirevision: instrument.mode,
  }
}

interface ScientificPlotPanelProps {
  instrument: InstrumentPresentation
  phase: InvestigationPhase
  onModeChange: (mode: InstrumentMode) => void
}

export function ScientificPlotPanel({
  instrument,
  phase,
  onModeChange,
}: ScientificPlotPanelProps) {
  return (
    <section className="instrument-stage" data-focus={phase === "measuring" || phase === "testing"}>
      <div className="instrument-header">
        <div>
          <span className="section-kicker">Measured evidence</span>
          <h2>{instrument.label}</h2>
          <p>{instrument.plot.annotation}</p>
        </div>
        <div className="instrument-readouts" aria-label="Current measurements">
          {instrument.readouts.map((readout) => (
            <span key={readout.label}>
              <small>{readout.label}</small>
              <strong className="telemetry">{readout.value}</strong>
              {readout.evidenceRef ? <code>{readout.evidenceRef}</code> : null}
            </span>
          ))}
        </div>
      </div>

      <div className="instrument-body">
        <Tabs
          value={instrument.mode}
          onValueChange={(value) => onModeChange(value as InstrumentMode)}
          className="instrument-tabs"
        >
          <TabsList variant="line" aria-label="Scientific instrument mode">
            {MODES.map((mode) => (
              <TabsTrigger key={mode.id} value={mode.id}>
                {mode.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="plot-frame" aria-label={`${instrument.label} synthetic demonstration plot`}>
          <Plot
            data={instrument.plot.traces.map(toPlotlyTrace)}
            layout={plotLayout(instrument)}
            config={{
              displayModeBar: false,
              responsive: true,
              scrollZoom: false,
              doubleClick: false,
              showTips: false,
            }}
            className="plotly-instrument"
            useResizeHandler
          />
        </div>
      </div>
    </section>
  )
}
