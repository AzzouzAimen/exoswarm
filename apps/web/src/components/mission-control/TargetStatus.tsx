"use client"

import { LockClosedIcon } from "@heroicons/react/24/outline"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import type { InvestigationPresentationState } from "./model/presentation-state"

interface TargetStatusProps {
  state: InvestigationPresentationState
  revealedIdentity?: string
  mobileDetails?: React.ReactNode
}

export function TargetStatus({
  state,
  revealedIdentity,
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
        <span className="demo-flag">Fixture playback</span>
      </div>

      <div className="mission-status">
        <span className="phase-readout">
          <span className="phase-index">{String(state.stageIndex).padStart(2, "0")}</span>
          {state.stageLabel}
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="sealed-readout" tabIndex={0}>
              <LockClosedIcon aria-hidden="true" />
              {revealedIdentity ?? "Official identity ███████"}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {revealedIdentity
              ? "Opened only after the independent result was saved."
              : "The agents cannot see the known catalog identity or answer."}
          </TooltipContent>
        </Tooltip>
        {mobileDetails}
      </div>
    </header>
  )
}
