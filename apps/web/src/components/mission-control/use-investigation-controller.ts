"use client"

import { useState } from "react"

import type { ClientError } from "@/lib/api"
import type { ArtifactMetadata, MissionControlSnapshot, TargetOption, ViewerTarget } from "@/lib/contracts"

import { DEMO_CASES, DEMO_CASE_LIST, type DemoCaseId } from "./demo/demo-cases"
import { useDemoPlayback } from "./demo/use-demo-playback"
import { useLiveInvestigation } from "./live/use-live-investigation"
import type { InstrumentMode } from "./model/presentation-state"
import { configuredDataMode, type DataMode } from "./runtime-mode"

export { configuredDataMode }

export interface InvestigationController {
  mode: DataMode
  targets: TargetOption[]
  viewerTargets: ViewerTarget[]
  targetsLoading: boolean
  state: ReturnType<typeof useLiveInvestigation>["state"]
  instrument: ReturnType<typeof useLiveInvestigation>["instrument"]
  snapshot?: MissionControlSnapshot
  artifacts: ArtifactMetadata[]
  step: number
  totalSteps: number
  isPlaying: boolean
  error: ClientError | null
  stageMarkers: ReadonlyArray<{ label: string; step: number }>
  start(targetId: string): Promise<void>
  setPlaying(value: boolean): void
  setStep(value: number): void
  replay(): void
  selectInstrumentMode(mode: InstrumentMode): void
  reset(): void
}

export function useInvestigationController(selectedId: string, running: boolean): InvestigationController {
  const [mode] = useState(configuredDataMode)
  const [fixtureInstrumentMode, setFixtureInstrumentMode] = useState<InstrumentMode>()
  const fixtureCase = DEMO_CASES[(selectedId in DEMO_CASES ? selectedId : "TARGET-C11") as DemoCaseId]
  const fixture = useDemoPlayback(fixtureCase, mode === "fixture" && running)
  const live = useLiveInvestigation(mode === "live")

  if (mode === "live") {
    return {
      ...live,
      stageMarkers: [
        { label: "Observe", step: 0 },
        { label: "Latest", step: live.totalSteps },
      ],
      selectInstrumentMode: (instrumentMode) => { void live.selectInstrumentMode(instrumentMode) },
    }
  }

  const targets: TargetOption[] = DEMO_CASE_LIST.map((item) => ({
    opaque_target_id: item.id,
    cached_lightcurve_available: true,
    cached_tpf_available: true,
    sector: item.sector,
    display_label: item.id,
  }))
  const viewerTargets: ViewerTarget[] = DEMO_CASE_LIST.flatMap((item) => item.reveal ? [{
    opaque_target_id: item.id,
    target_name: item.reveal.targetName,
    tic_id: item.reveal.catalogId.replace(/^TIC\s+/i, ""),
    catalog_disposition: item.reveal.catalogDisposition,
    catalog_source: item.reveal.sourceLabel,
    catalog_source_url: "https://exoplanetarchive.ipac.caltech.edu/",
    known_values: {},
  }] : [])
  return {
    mode: "fixture",
    targets,
    viewerTargets,
    targetsLoading: false,
    state: fixture.state,
    instrument: fixtureInstrumentMode ? fixtureCase.instruments[fixtureInstrumentMode] : fixture.state.instrument,
    snapshot: undefined,
    artifacts: [],
    step: fixture.step,
    totalSteps: fixture.totalSteps,
    isPlaying: fixture.isPlaying,
    error: null,
    stageMarkers: fixtureCase.stageMarkers,
    start: async () => {
      setFixtureInstrumentMode(undefined)
      fixture.start()
    },
    setPlaying: (value) => {
      setFixtureInstrumentMode(undefined)
      fixture.setIsPlaying(value)
    },
    setStep: (value) => {
      setFixtureInstrumentMode(undefined)
      fixture.setStep(value)
    },
    replay: () => {
      setFixtureInstrumentMode(undefined)
      fixture.replay()
    },
    selectInstrumentMode: setFixtureInstrumentMode,
    reset: () => {
      setFixtureInstrumentMode(undefined)
      fixture.setStep(0)
    },
  }
}
