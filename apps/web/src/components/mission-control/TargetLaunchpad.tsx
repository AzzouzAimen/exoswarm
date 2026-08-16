"use client"

import {
  ArrowRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleStackIcon,
  EyeIcon,
} from "@heroicons/react/24/outline"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import type { DataMode } from "./runtime-mode"
import {
  targetPage,
  targetPageCount,
  targetPageForSelection,
  TARGET_PAGE_SIZE,
  type LaunchTargetView,
} from "./view-models"

export function TargetLaunchpad({
  selectedId,
  targets,
  mode,
  loading,
  error,
  onSelectedIdChange,
  onStart,
}: {
  selectedId: string
  targets: LaunchTargetView[]
  mode: DataMode
  loading: boolean
  error?: string
  onSelectedIdChange: (id: string) => void
  onStart: () => void
}) {
  const selectionPage = targetPageForSelection(targets, selectedId)
  const [page, setPage] = useState(selectionPage)
  const pageCount = targetPageCount(targets)
  const visibleTargets = targetPage(targets, page)

  const changePage = (nextPage: number) => {
    const boundedPage = Math.min(Math.max(0, nextPage), pageCount - 1)
    setPage(boundedPage)
    const nextTargets = targetPage(targets, boundedPage)
    if (!nextTargets.some((target) => target.id === selectedId)) {
      const firstAvailable = nextTargets.find((target) => target.available)
      if (firstAvailable) onSelectedIdChange(firstAvailable.id)
    }
  }

  return (
    <section className="launchpad" aria-labelledby="launchpad-title">
      <div className="launchpad-copy">
        <span className="section-kicker">Viewer-informed · agents blind</span>
        <h1 id="launchpad-title">Choose an observation</h1>
        <p>
          Watch a small team of agents choose the next useful check while deterministic code owns
          every measurement.
        </p>
      </div>

      <ToggleGroup
        type="single"
        value={selectedId}
        onValueChange={(value) => value && onSelectedIdChange(value)}
        orientation="vertical"
        className="launchpad-targets"
        aria-label="Observations"
      >
        {visibleTargets.map((target, index) => (
          <ToggleGroupItem key={target.id} value={target.id} className="launchpad-target" disabled={!target.available}>
            <span className="launchpad-target-index telemetry">
              {String(page * TARGET_PAGE_SIZE + index + 1).padStart(2, "0")}
            </span>
            <span className="launchpad-target-copy">
              <strong>{target.id}</strong>
              <small>{target.observationLabel}</small>
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="launchpad-official" tabIndex={0}>
                  <EyeIcon aria-hidden="true" />
                  {target.officialIdentity ?? "Official identity unavailable"}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                Official identity is visible to you. Agents receive only the opaque target ID.
              </TooltipContent>
            </Tooltip>
            <span className="launchpad-ready">
              <i aria-hidden="true" /> {target.available ? "Ready" : "Unavailable"}
            </span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {pageCount > 1 ? (
        <nav className="launchpad-pagination" aria-label="Observation pages">
          <span className="telemetry">
            {page * TARGET_PAGE_SIZE + 1}–{Math.min((page + 1) * TARGET_PAGE_SIZE, targets.length)} of {targets.length}
          </span>
          <div>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              aria-label="Previous observations"
              disabled={page === 0}
              onClick={() => changePage(page - 1)}
            >
              <ChevronLeftIcon aria-hidden="true" />
            </Button>
            <span aria-live="polite">Page {page + 1} of {pageCount}</span>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              aria-label="Next observations"
              disabled={page >= pageCount - 1}
              onClick={() => changePage(page + 1)}
            >
              <ChevronRightIcon aria-hidden="true" />
            </Button>
          </div>
        </nav>
      ) : null}

      <div className="launchpad-action">
        <div>
          <CircleStackIcon aria-hidden="true" />
          <span>
            <strong>{mode === "live" ? "API run" : "Recorded scenario"}</strong>
            <small>{error ?? (mode === "live" ? "Starts an investigation and streams each state transition." : "Replays a saved investigation sequence.")}</small>
          </span>
        </div>
        <Button type="button" size="lg" onClick={onStart} disabled={loading || !selectedId || !targets.some((target) => target.id === selectedId && target.available)}>
          Start blind investigation
          <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
        </Button>
      </div>
    </section>
  )
}
