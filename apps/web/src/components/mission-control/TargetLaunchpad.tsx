"use client"

import { ArrowRightIcon, CircleStackIcon, EyeIcon } from "@heroicons/react/24/outline"

import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { DEMO_CASE_LIST, type DemoCaseId } from "./demo/demo-cases"

export function TargetLaunchpad({
  selectedId,
  onSelectedIdChange,
  onStart,
}: {
  selectedId: DemoCaseId
  onSelectedIdChange: (id: DemoCaseId) => void
  onStart: () => void
}) {
  return (
    <section className="launchpad" aria-labelledby="launchpad-title">
      <div className="launchpad-copy">
        <span className="section-kicker">Blind investigation demo</span>
        <h1 id="launchpad-title">Choose an observation</h1>
        <p>
          Watch a small team of agents choose the next useful check while deterministic code owns
          every measurement.
        </p>
      </div>

      <ToggleGroup
        type="single"
        value={selectedId}
        onValueChange={(value) => value && onSelectedIdChange(value as DemoCaseId)}
        orientation="vertical"
        className="launchpad-targets"
        aria-label="Observations"
      >
        {DEMO_CASE_LIST.map((demoCase) => (
          <ToggleGroupItem key={demoCase.id} value={demoCase.id} className="launchpad-target">
            <span className="launchpad-target-index telemetry">
              {String(DEMO_CASE_LIST.indexOf(demoCase) + 1).padStart(2, "0")}
            </span>
            <span className="launchpad-target-copy">
              <strong>{demoCase.id}</strong>
              <small>Cached TESS observation · Sector {demoCase.sector}</small>
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="launchpad-official" tabIndex={0}>
                  <EyeIcon aria-hidden="true" />
                  {demoCase.reveal?.targetName ?? "Official identity unavailable"}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                Official identity is visible to you. Agents receive only the opaque target ID.
              </TooltipContent>
            </Tooltip>
            <span className="launchpad-ready">
              <i aria-hidden="true" /> Ready
            </span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <div className="launchpad-action">
        <div>
          <CircleStackIcon aria-hidden="true" />
          <span>
            <strong>Fast demo mode</strong>
            <small>Replays cached backend-aligned fixtures; live integration follows this UI sweep.</small>
          </span>
        </div>
        <Button type="button" size="lg" onClick={onStart}>
          Start blind investigation
          <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
        </Button>
      </div>
    </section>
  )
}
