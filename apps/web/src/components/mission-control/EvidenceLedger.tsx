"use client"

import { ClockIcon } from "@heroicons/react/24/outline"

import { AnimatedList } from "@/components/ui/animated-list"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"

import type { TimelineRecord } from "./model/presentation-state"

export function EvidenceLedger({
  events,
  currentStep,
  onSelect,
}: {
  events: TimelineRecord[]
  currentStep: number
  onSelect: (step: number) => void
}) {
  const latest = events.at(-1)
  const visibleEvents = events.slice(-8).reverse()

  return (
    <section className="run-log" aria-label="Investigation run log">
      <Popover>
        <PopoverTrigger asChild>
          <button type="button" className="run-log-trigger">
            <ClockIcon aria-hidden="true" />
            <span>
              <small>Run log · {events.length}</small>
              <strong>{latest?.headline ?? "Waiting for first action"}</strong>
            </span>
            {latest ? <time className="telemetry">{latest.timestamp}</time> : null}
          </button>
        </PopoverTrigger>
        <PopoverContent className="run-log-popover" side="top" align="end" sideOffset={12}>
          <PopoverHeader>
            <PopoverTitle>Run log</PopoverTitle>
            <PopoverDescription>Every decision, measurement, and saved result in order.</PopoverDescription>
          </PopoverHeader>
          {visibleEvents.length ? (
            <AnimatedList className="run-log-events">
              {visibleEvents.map((event) => (
                <button
                  type="button"
                  key={event.id}
                  className="run-log-event"
                  data-tone={event.tone}
                  data-current={event.sequence === currentStep}
                  onClick={() => onSelect(event.sequence)}
                >
                  <time className="telemetry">{event.timestamp}</time>
                  <span>{event.actor}</span>
                  <strong>{event.headline}</strong>
                  {event.evidenceRef ? <code>{event.evidenceRef}</code> : null}
                </button>
              ))}
            </AnimatedList>
          ) : (
            <p className="run-log-empty">The first action will appear here.</p>
          )}
        </PopoverContent>
      </Popover>
    </section>
  )
}
