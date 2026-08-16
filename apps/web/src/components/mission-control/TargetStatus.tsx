"use client"

import { EyeIcon } from "@heroicons/react/24/outline"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import type { InvestigationPresentationState } from "./model/presentation-state"

interface TargetStatusProps {
  state: InvestigationPresentationState
  officialIdentity?: string
  mobileDetails?: React.ReactNode
}

export function TargetStatus({
  state,
  officialIdentity,
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
            <span className="official-readout" tabIndex={0}>
              <EyeIcon aria-hidden="true" />
              <span>Official: {officialIdentity ?? "Not available"}</span>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            Visible to you for context. Agents receive only the opaque target ID and cannot see this identity.
          </TooltipContent>
        </Tooltip>
        {mobileDetails}
      </div>
    </header>
  )
}
