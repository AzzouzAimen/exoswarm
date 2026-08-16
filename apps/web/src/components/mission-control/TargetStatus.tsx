"use client"

import { EyeIcon } from "@heroicons/react/24/outline"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { ViewerTarget } from "@/lib/contracts"

import type { InvestigationPresentationState } from "./model/presentation-state"

interface TargetStatusProps {
  state: InvestigationPresentationState
  viewerTarget?: ViewerTarget
  source: "live" | "fixture"
  mobileDetails?: React.ReactNode
}

export function TargetStatus({
  state,
  viewerTarget,
  source,
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
        <span className="demo-flag">{source === "live" ? "API run" : "Recorded scenario"}</span>
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
              <span>
                <strong>{viewerTarget?.target_name ?? "Loading official reference"}</strong>
                {viewerTarget ? <small>{viewerTarget.catalog_disposition.replaceAll("_", " ").toLowerCase()}</small> : null}
              </span>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {viewerTarget ? `Viewer reference: TIC ${viewerTarget.tic_id}. Agents receive only the opaque target ID and independent evidence.` : "Loading the separate viewer-only catalog reference."}
          </TooltipContent>
        </Tooltip>
        {mobileDetails}
      </div>
    </header>
  )
}
