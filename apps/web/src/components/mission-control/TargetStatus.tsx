"use client"

import { LockClosedIcon, ViewfinderCircleIcon } from "@heroicons/react/24/outline"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import type { InvestigationPresentationState } from "./model/presentation-state"

interface TargetStatusProps {
  state: InvestigationPresentationState
  xRayEnabled: boolean
  onToggleXRay: () => void
  mobileDetails?: React.ReactNode
}

export function TargetStatus({
  state,
  xRayEnabled,
  onToggleXRay,
  mobileDetails,
}: TargetStatusProps) {
  return (
    <header className="mission-header">
      <div className="mission-brand" aria-label="ExoSwarm mission control">
        <span className="mission-mark" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>EXO<span>SWARM</span></span>
      </div>

      <div className="mission-target">
        <span className="telemetry">{state.target.id}</span>
        <span className="target-rule" aria-hidden="true" />
        <span>{state.target.sector}</span>
        <span className="demo-flag">Demo data</span>
      </div>

      <div className="mission-status">
        <span className="phase-readout">
          <span className="phase-index">{String(state.stageIndex).padStart(2, "0")}</span>
          {state.stageLabel}
        </span>
        <span className="sealed-readout">
          <LockClosedIcon aria-hidden="true" />
          {state.lock ? "Saved" : "Catalog hidden"}
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant={xRayEnabled ? "secondary" : "outline"}
              size="sm"
              aria-pressed={xRayEnabled}
              onClick={onToggleXRay}
            >
              <ViewfinderCircleIcon data-icon="inline-start" aria-hidden="true" />
              X-RAY
            </Button>
          </TooltipTrigger>
          <TooltipContent>Show how decisions are checked</TooltipContent>
        </Tooltip>
        {mobileDetails}
      </div>
    </header>
  )
}
