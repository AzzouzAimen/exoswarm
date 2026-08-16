"use client"

import { useState } from "react"

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
  const [revealed, setRevealed] = useState(false)
  const [isEvidenceCollapsed, setIsEvidenceCollapsed] = useState(true)
  const [inspectedInstrumentMode, setInspectedInstrumentMode] = useState<InstrumentMode>()
  const demoCase = DEMO_CASES[selectedCaseId]
  const playback = useDemoPlayback(demoCase, experience === "running")
  const { state } = playback
  const isComplete = experience === "running" && playback.step >= playback.totalSteps
  const isEvidenceDisplayCollapsed = isComplete || isEvidenceCollapsed

  const startInvestigation = () => {
    setRevealed(false)
    setInspectedInstrumentMode(undefined)
    setIsEvidenceCollapsed(true)
    setExperience("running")
    playback.start()
  }

  const restartSelection = () => {
    setRevealed(false)
    setInspectedInstrumentMode(undefined)
    setExperience("selecting")
    playback.setStep(0)
  }

  const selectInstrumentMode = (mode: InstrumentMode) => {
    playback.setStep(playback.step)
    setInspectedInstrumentMode(mode)
  }

  const selectStep = (step: number) => {
    if (step < playback.totalSteps) setRevealed(false)
    setInspectedInstrumentMode(undefined)
    playback.setStep(step)
  }

  const setPlaying = (playing: boolean) => {
    setInspectedInstrumentMode(undefined)
    playback.setIsPlaying(playing)
  }

  const replay = () => {
    setRevealed(false)
    setInspectedInstrumentMode(undefined)
    playback.replay()
  }

  return (
    <main
      className={cn(
        "mission-shell",
        experience === "selecting" && "mission-is-selecting",
        (state.phase === "measuring" || state.phase === "testing") && "instrument-is-focus",
        isComplete && "investigation-is-complete",
      )}
      data-evidence-collapsed={isEvidenceDisplayCollapsed}
    >
      <TargetStatus
        state={state}
        revealedIdentity={revealed ? demoCase.reveal?.targetName : undefined}
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
            </div>
            {isComplete ? (
              <LockRevealPanel
                demoCase={demoCase}
                state={state}
                revealed={revealed}
                onReveal={() => setRevealed(true)}
                onRestart={restartSelection}
              />
            ) : null}
          </section>

          <ScientificPlotPanel
            instrument={
              inspectedInstrumentMode ? demoCase.instruments[inspectedInstrumentMode] : state.instrument
            }
            phase={state.phase}
            onModeChange={selectInstrumentMode}
            isCollapsed={isEvidenceDisplayCollapsed}
            onCollapsedChange={setIsEvidenceCollapsed}
          />

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
            <RunIntegrity result={demoCase.result} />
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
