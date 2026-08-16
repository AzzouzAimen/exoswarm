"use client"

import { EyeIcon } from "@heroicons/react/24/outline"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { AgentTrace } from "./AgentTrace"
import { CentralOrbitScene, OrbitSceneStatus } from "./CentralOrbitScene"
import { DEMO_CASES, type DemoCaseId } from "./demo/demo-cases"
import { useDemoPlayback } from "./demo/use-demo-playback"
import { EvidenceLedger } from "./EvidenceLedger"
import { HypothesisPanel } from "./HypothesisPanel"
import { LockRevealPanel } from "./LockRevealPanel"
import { MobileInvestigationSheet } from "./MobileInvestigationSheet"
import { PlaybackControls } from "./PlaybackControls"
import { RunIntegrity } from "./RunIntegrity"
import { ScientificPlotPanel } from "./ScientificPlotPanel"
import { TargetLaunchpad } from "./TargetLaunchpad"
import { TargetStatus } from "./TargetStatus"
import type { InstrumentMode } from "./model/presentation-state"

export function MissionControlShell() {
  const [selectedCaseId, setSelectedCaseId] = useState<DemoCaseId>("TARGET-C11")
  const [experience, setExperience] = useState<"selecting" | "running">("selecting")
  const [resultsOpen, setResultsOpen] = useState(false)
  const [isEvidenceCollapsed, setIsEvidenceCollapsed] = useState(true)
  const [inspectedInstrumentMode, setInspectedInstrumentMode] = useState<InstrumentMode>()
  const demoCase = DEMO_CASES[selectedCaseId]
  const playback = useDemoPlayback(demoCase, experience === "running")
  const { state } = playback
  const isComplete = experience === "running" && playback.step >= playback.totalSteps
  const isResultDialogOpen = isComplete && resultsOpen
  const isEvidenceDisplayCollapsed = isComplete || isEvidenceCollapsed

  const startInvestigation = () => {
    setResultsOpen(true)
    setInspectedInstrumentMode(undefined)
    setIsEvidenceCollapsed(true)
    setExperience("running")
    playback.start()
  }

  const restartSelection = () => {
    setResultsOpen(false)
    setInspectedInstrumentMode(undefined)
    setExperience("selecting")
    playback.setStep(0)
  }

  const selectInstrumentMode = (mode: InstrumentMode) => {
    playback.setStep(playback.step)
    setInspectedInstrumentMode(mode)
  }

  const selectStep = (step: number) => {
    if (step >= playback.totalSteps) setResultsOpen(true)
    setInspectedInstrumentMode(undefined)
    playback.setStep(step)
  }

  const setPlaying = (playing: boolean) => {
    if (playing) setResultsOpen(true)
    setInspectedInstrumentMode(undefined)
    playback.setIsPlaying(playing)
  }

  const replay = () => {
    setResultsOpen(true)
    setInspectedInstrumentMode(undefined)
    playback.replay()
  }

  return (
    <main
      className={cn(
        "mission-shell",
        experience === "selecting" && "mission-is-selecting",
        (state.phase === "measuring" || state.phase === "testing") && "instrument-is-focus",
        isResultDialogOpen && "results-are-open",
      )}
      data-evidence-collapsed={isEvidenceDisplayCollapsed}
    >
      <TargetStatus
        state={state}
        officialIdentity={demoCase.reveal?.targetName}
        mobileDetails={<MobileInvestigationSheet state={state} />}
      />

      <CentralOrbitScene state={state} />

      {experience === "selecting" ? (
        <TargetLaunchpad
          selectedId={selectedCaseId}
          onSelectedIdChange={setSelectedCaseId}
          onStart={startInvestigation}
        />
      ) : (
        <>
          <section className="investigation-stage" aria-label="Live investigation">
            <div className="investigation-briefing">
              <AgentTrace state={state} currentStep={playback.step} onSelect={selectStep} />
            </div>

            <div className="mission-top-actions">
              <OrbitSceneStatus state={state} />
              <HypothesisPanel hypotheses={state.hypotheses} />
              {isComplete && !resultsOpen ? (
                <Button type="button" className="view-result-button" onClick={() => setResultsOpen(true)}>
                  <EyeIcon aria-hidden="true" />
                  View result
                </Button>
              ) : null}
            </div>
            {isResultDialogOpen ? (
              <LockRevealPanel
                demoCase={demoCase}
                state={state}
                onClose={() => setResultsOpen(false)}
                onRestart={restartSelection}
              />
            ) : null}
          </section>

          {!isResultDialogOpen ? (
            <ScientificPlotPanel
              instrument={
                inspectedInstrumentMode ? demoCase.instruments[inspectedInstrumentMode] : state.instrument
              }
              phase={state.phase}
              onModeChange={selectInstrumentMode}
              isCollapsed={isEvidenceDisplayCollapsed}
              onCollapsedChange={setIsEvidenceCollapsed}
            />
          ) : null}

          <footer className="mission-footer">
            <PlaybackControls
              step={playback.step}
              totalSteps={playback.totalSteps}
              isPlaying={playback.isPlaying}
              onPlayingChange={setPlaying}
              onStepChange={selectStep}
              onReplay={replay}
              stageMarkers={demoCase.stageMarkers}
            />
            {!isResultDialogOpen ? <RunIntegrity result={demoCase.result} /> : null}
            <EvidenceLedger
              events={state.timeline}
              currentStep={playback.step}
              onSelect={selectStep}
            />
          </footer>
        </>
      )}
    </main>
  )
}
