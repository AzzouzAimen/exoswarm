"use client"

import { ChevronDownIcon } from "@heroicons/react/24/outline"
import dynamic from "next/dynamic"
import type { Layout } from "plotly.js"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import type {
  InstrumentMode,
  InstrumentPresentation,
  InvestigationPhase,
} from "./model/presentation-state"
import { plotContentState, toPlotlyTrace } from "./scientific-plot"

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false })

const MODES: Array<{ id: InstrumentMode; label: string; help: string }> = [
  { id: "raw", label: "Brightness", help: "The observation before repeat-pattern analysis." },
  { id: "bls", label: "Repeat search", help: "How strongly each possible interval matches repeating dips." },
  { id: "phase-fold", label: "Dips lined up", help: "Repeated cycles stacked to show the shared event shape." },
  { id: "odd-even", label: "Odd / even", help: "Compares every other event to catch two-star systems." },
  { id: "secondary", label: "Second dip", help: "Searches for another eclipse between primary events." },
  { id: "harmonic", label: "Alt timing", help: "Checks whether half or double the interval fits better." },
]

function plotLayout(instrument: InstrumentPresentation): Partial<Layout> {
  return {
    autosize: true,
    height: 176,
    margin: { l: 58, r: 20, t: 14, b: 44 },
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
  isCollapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

export function ScientificPlotPanel({
  instrument,
  phase,
  onModeChange,
  isCollapsed,
  onCollapsedChange,
}: ScientificPlotPanelProps) {
  const contentState = plotContentState(instrument)
  const primaryReadouts = instrument.readouts.slice(0, 4)
  const evidenceRefs = [...new Set(instrument.readouts.flatMap((readout) => readout.evidenceRef ? [readout.evidenceRef] : []))]
  return (
    <section
      className="instrument-stage"
      data-collapsed={isCollapsed}
      data-focus={phase === "measuring" || phase === "testing"}
    >
      <div className="instrument-header">
        <div>
          <div className="instrument-title-row">
            <span className="section-kicker">Measured evidence</span>
            <button
              type="button"
              className="instrument-collapse"
              aria-expanded={!isCollapsed}
              aria-label={isCollapsed ? "Expand measured evidence" : "Collapse measured evidence"}
              onClick={() => onCollapsedChange(!isCollapsed)}
            >
              <ChevronDownIcon aria-hidden="true" />
            </button>
          </div>
          <h2>{instrument.label}</h2>
          <p>{instrument.plot.annotation}</p>
        </div>
        <div className="instrument-readouts" aria-label="Current measurements">
          {primaryReadouts.map((readout) => (
            <span key={readout.label} title={readout.evidenceRef ? `Source: ${readout.evidenceRef}` : undefined}>
              <small>{readout.label}</small>
              <strong className="telemetry">{readout.value}</strong>
            </span>
          ))}
        </div>
        {evidenceRefs[0] ? (
          <div className="instrument-provenance">
            <small>Evidence source</small>
            <code title={evidenceRefs[0]}>{evidenceRefs[0].slice(-12)}</code>
          </div>
        ) : null}
      </div>

      <div className="instrument-body">
        <Tabs
          value={instrument.mode}
          onValueChange={(value) => onModeChange(value as InstrumentMode)}
          className="instrument-tabs"
        >
          <TabsList variant="line" aria-label="Scientific instrument mode">
            {MODES.map((mode) => (
              <Tooltip key={mode.id}>
                <TooltipTrigger asChild>
                  <span className="instrument-tab-tooltip">
                    <TabsTrigger value={mode.id} className="instrument-tab-trigger">
                      {mode.label}
                    </TabsTrigger>
                  </span>
                </TooltipTrigger>
                <TooltipContent>{mode.help}</TooltipContent>
              </Tooltip>
            ))}
          </TabsList>
        </Tabs>
        <div className="plot-frame" aria-label={`${instrument.label} scientific visualization`}>
          {contentState === "chart" ? <Plot
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
          /> : contentState === "readouts"
            ? <div className="plot-unavailable" role="status">{instrument.plot.annotation || "This diagnostic is available as measured readouts."}</div>
            : <div className="plot-unavailable" role="status">{instrument.unavailableReason ?? instrument.plot.annotation}</div>}
        </div>
      </div>
    </section>
  )
}
