"use client"

import { EyeIcon } from "@heroicons/react/24/outline"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { AgentTrace } from "./AgentTrace"
import { CentralOrbitScene, OrbitSceneStatus } from "./CentralOrbitScene"
import { DEMO_CASES, type DemoCaseId } from "./demo/demo-cases"
import { EvidenceLedger } from "./EvidenceLedger"
import { ResultComparisonPanel } from "./ResultComparisonPanel"
import { MobileInvestigationSheet } from "./MobileInvestigationSheet"
import type { InstrumentMode } from "./model/presentation-state"
import { RunIntegrity } from "./RunIntegrity"
import { ScientificPlotPanel } from "./ScientificPlotPanel"
import { TargetLaunchpad } from "./TargetLaunchpad"
import { TargetStatus } from "./TargetStatus"
import { useInvestigationController } from "./use-investigation-controller"
import {
  fixtureResultComparisonView,
  launchTargets,
  liveIntegrityView,
  liveResultComparisonView,
} from "./view-models"

export function MissionControlShell() {
  const [selectedId, setSelectedId] = useState("TARGET-C11")
  const [experience, setExperience] = useState<"selecting" | "running">("selecting")
  const [resultsOpen, setResultsOpen] = useState(false)
  const [isEvidenceCollapsed, setIsEvidenceCollapsed] = useState(true)
  const controller = useInvestigationController(selectedId, experience === "running")
  const { state } = controller
  const fixtureCase = DEMO_CASES[(selectedId in DEMO_CASES ? selectedId : "TARGET-C11") as DemoCaseId]
  const targets = launchTargets(controller.targets, controller.viewerTargets, controller.mode === "fixture" ? DEMO_CASES : undefined)
  const effectiveSelectedId = targets.some((target) => target.id === selectedId)
    ? selectedId
    : targets.find((target) => target.available)?.id ?? ""
  const viewerTarget = controller.viewerTargets.find((target) => target.opaque_target_id === effectiveSelectedId)
  const liveComplete = controller.snapshot ? ["READY_TO_LOCK", "RESULT_LOCKED", "REVEALED", "INSUFFICIENT_EVIDENCE", "REJECTED", "FAILED", "BUDGET_EXHAUSTED"].includes(controller.snapshot.status) : false
  const isRunningExperience = experience === "running" || (controller.mode === "live" && Boolean(controller.snapshot))
  const isComplete = isRunningExperience && (controller.mode === "live" ? liveComplete : controller.step >= controller.totalSteps)
  const isResultDialogOpen = isComplete && resultsOpen
  const isEvidenceDisplayCollapsed = isEvidenceCollapsed

  const startInvestigation = async () => {
    setResultsOpen(true)
    setIsEvidenceCollapsed(false)
    try {
      await controller.start(effectiveSelectedId)
      setExperience("running")
    } catch {
      // The controller keeps the typed live failure visible on the launchpad.
    }
  }

  const restartSelection = () => {
    setResultsOpen(false)
    setExperience("selecting")
    controller.reset()
  }

  const reviewInvestigation = () => {
    setResultsOpen(false)
    setIsEvidenceCollapsed(false)
  }

  const selectInstrumentMode = (mode: InstrumentMode) => {
    controller.setStep(controller.step)
    controller.selectInstrumentMode(mode)
  }

  const selectStep = (nextStep: number) => {
    if (nextStep >= controller.totalSteps && isComplete) setResultsOpen(true)
    controller.setStep(nextStep)
  }

  const resultView = viewerTarget
    ? controller.mode === "live" && controller.snapshot
      ? liveResultComparisonView(controller.snapshot, controller.artifacts, viewerTarget)
      : fixtureResultComparisonView(fixtureCase, viewerTarget)
    : undefined
  const integrity = controller.mode === "live" && controller.snapshot
    ? liveIntegrityView(controller.snapshot)
    : { agentCalls: fixtureCase.result.agentCalls, toolCalls: fixtureCase.result.toolCalls }
  return (
    <main
      className={cn(
        "mission-shell",
        !isRunningExperience && "mission-is-selecting",
        (state.phase === "measuring" || state.phase === "testing") && "instrument-is-focus",
        isResultDialogOpen && "results-are-open",
      )}
      data-evidence-collapsed={isEvidenceDisplayCollapsed}
    >
      <TargetStatus state={state} source={controller.mode} viewerTarget={viewerTarget} mobileDetails={<MobileInvestigationSheet state={state} />} />
      <CentralOrbitScene state={state} />

      {!isRunningExperience ? (
        <TargetLaunchpad
          selectedId={effectiveSelectedId}
          targets={targets}
          mode={controller.mode}
          loading={controller.targetsLoading}
          error={controller.error?.message}
          onSelectedIdChange={setSelectedId}
          onStart={() => { void startInvestigation() }}
        />
      ) : (
        <>
          <section className="investigation-stage" aria-label="Live investigation">
            <div className="investigation-briefing"><AgentTrace state={state} currentStep={controller.step} onSelect={selectStep} /></div>
            <div className="mission-top-actions">
              <OrbitSceneStatus state={state} />
              {isComplete && !resultsOpen ? <Button type="button" className="view-result-button" onClick={() => setResultsOpen(true)}><EyeIcon aria-hidden="true" />View result</Button> : null}
            </div>
            {isResultDialogOpen && resultView ? (
              <ResultComparisonPanel
                runId={state.run.id}
                view={resultView}
                error={controller.error?.message}
                onClose={reviewInvestigation}
                onRestart={restartSelection}
              />
            ) : null}
          </section>

          {!isResultDialogOpen ? <ScientificPlotPanel instrument={controller.instrument} phase={state.phase} onModeChange={selectInstrumentMode} isCollapsed={isEvidenceDisplayCollapsed} onCollapsedChange={setIsEvidenceCollapsed} /> : null}

          <footer className="mission-footer">
            <EvidenceLedger events={state.timeline} currentStep={controller.step} onSelect={selectStep} />
            {!isResultDialogOpen ? <RunIntegrity result={integrity} /> : null}
          </footer>
        </>
      )}
    </main>
  )
}
