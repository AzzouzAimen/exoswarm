"use client"

import {
  ArrowPathIcon,
  ForwardIcon,
  PauseIcon,
  PlayIcon,
  StopIcon,
} from "@heroicons/react/24/outline"

import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { DEMO_STAGE_MARKERS } from "./demo/demo-investigation.fixture"

interface PlaybackControlsProps {
  step: number
  totalSteps: number
  isPlaying: boolean
  onPlayingChange: (playing: boolean) => void
  onStepChange: (step: number) => void
  onReplay: () => void
}

function IconControl({
  label,
  children,
  ...props
}: React.ComponentProps<typeof Button> & { label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button type="button" variant="ghost" size="icon-sm" {...props}>
          {children}
          <span className="sr-only">{label}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

export function PlaybackControls({
  step,
  totalSteps,
  isPlaying,
  onPlayingChange,
  onStepChange,
  onReplay,
}: PlaybackControlsProps) {
  return (
    <section className="playback-controls" aria-label="Demo investigation playback">
      <div className="playback-buttons">
        <IconControl
          label={isPlaying ? "Pause investigation" : "Play investigation"}
          onClick={() => onPlayingChange(!isPlaying)}
        >
          {isPlaying ? <PauseIcon aria-hidden="true" /> : <PlayIcon aria-hidden="true" />}
        </IconControl>
        <IconControl
          label="Step forward"
          disabled={step >= totalSteps}
          onClick={() => onStepChange(step + 1)}
        >
          <ForwardIcon aria-hidden="true" />
        </IconControl>
        <IconControl label="Replay from start" onClick={onReplay}>
          <ArrowPathIcon aria-hidden="true" />
        </IconControl>
      </div>

      <div className="scrubber-stack">
        <div className="stage-markers" aria-label="Investigation stages">
          {DEMO_STAGE_MARKERS.map((marker, index) => (
            <button
              type="button"
              key={marker.label}
              data-passed={step >= marker.step}
              data-current={
                step >= marker.step &&
                (index === DEMO_STAGE_MARKERS.length - 1 || step < DEMO_STAGE_MARKERS[index + 1].step)
              }
              onClick={() => onStepChange(marker.step)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              {marker.label}
            </button>
          ))}
        </div>
        <Slider
          min={0}
          max={totalSteps}
          step={1}
          value={[step]}
          onValueChange={(value) => onStepChange(value[0] ?? 0)}
          aria-label="Investigation timeline"
        />
      </div>

      <div className="playback-position telemetry">
        {step >= totalSteps ? <StopIcon aria-hidden="true" /> : null}
        {String(step).padStart(2, "0")} / {String(totalSteps).padStart(2, "0")}
      </div>
    </section>
  )
}
