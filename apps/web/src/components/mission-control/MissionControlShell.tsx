"use client"

import { useState } from "react"

import { cn } from "@/lib/utils"

import { AgentTrace } from "./AgentTrace"
import { CentralOrbitScene, OrbitSceneStatus } from "./CentralOrbitScene"
import { DEMO_INSTRUMENTS } from "./demo/demo-investigation.fixture"
import { useDemoPlayback } from "./demo/use-demo-playback"
import { EvidenceLedger } from "./EvidenceLedger"
import { HypothesisPanel } from "./HypothesisPanel"
import { LockRevealPanel } from "./LockRevealPanel"
import { MobileInvestigationSheet } from "./MobileInvestigationSheet"
import { PlaybackControls } from "./PlaybackControls"
import { ScientificPlotPanel } from "./ScientificPlotPanel"
import { TargetStatus } from "./TargetStatus"
import { XRayOverlay } from "./XRayOverlay"
import type { InstrumentMode } from "./model/presentation-state"

export function MissionControlShell() {
  const playback = useDemoPlayback()
  const [xRayEnabled, setXRayEnabled] = useState(false)
  const [isEvidenceCollapsed, setIsEvidenceCollapsed] = useState(true)
  const [inspectedInstrumentMode, setInspectedInstrumentMode] = useState<InstrumentMode>()
  const { state } = playback

  const selectInstrumentMode = (mode: InstrumentMode) => {
    playback.setStep(playback.step)
    setInspectedInstrumentMode(mode)
  }

  const selectStep = (step: number) => {
    setInspectedInstrumentMode(undefined)
    playback.setStep(step)
  }

  const setPlaying = (playing: boolean) => {
    setInspectedInstrumentMode(undefined)
    playback.setIsPlaying(playing)
  }

  const replay = () => {
    setInspectedInstrumentMode(undefined)
    playback.replay()
  }

  return (
    <main
      className={cn(
        "mission-shell",
        (state.phase === "measuring" || state.phase === "testing") && "instrument-is-focus",
        state.phase === "locked" && "investigation-is-locked",
      )}
      data-evidence-collapsed={isEvidenceCollapsed}
    >
      <TargetStatus
        state={state}
        xRayEnabled={xRayEnabled}
        onToggleXRay={() => setXRayEnabled((enabled) => !enabled)}
        mobileDetails={<MobileInvestigationSheet state={state} />}
      />

      <CentralOrbitScene state={state} />

      <section className="investigation-stage" aria-label="Live investigation">
        <div className="investigation-briefing">
          <AgentTrace state={state} currentStep={playback.step} onSelect={selectStep} />
        </div>

        <div className="mission-top-actions">
          <OrbitSceneStatus state={state} />
          <HypothesisPanel hypotheses={state.hypotheses} />
        </div>
        <LockRevealPanel state={state} />
        <XRayOverlay visible={xRayEnabled} budget={state.evidenceBudget} />
      </section>

      <ScientificPlotPanel
        instrument={
          inspectedInstrumentMode ? DEMO_INSTRUMENTS[inspectedInstrumentMode] : state.instrument
        }
        phase={state.phase}
        onModeChange={selectInstrumentMode}
        isCollapsed={isEvidenceCollapsed}
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
        />
        <EvidenceLedger
          events={state.timeline}
          currentStep={playback.step}
          onSelect={selectStep}
        />
      </footer>
    </main>
  )
}
