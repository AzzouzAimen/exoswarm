"use client"

import { ChevronDownIcon, QuestionMarkCircleIcon } from "@heroicons/react/24/outline"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"

import type { HypothesisPresentation } from "./model/presentation-state"

const STATE_LABELS: Record<HypothesisPresentation["state"], string> = {
  unresolved: "Still possible",
  supported: "Fits evidence",
  "under-test": "Testing",
  weakened: "Less likely",
}

export function HypothesisPanel({ hypotheses }: { hypotheses: HypothesisPresentation[] }) {
  return (
    <aside className="possible-causes-control" aria-label="Possible causes">
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="xs">
            <QuestionMarkCircleIcon data-icon="inline-start" />
            Possible causes
            <ChevronDownIcon className="possible-causes-chevron" data-icon="inline-end" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="possible-causes-popover"
          side="bottom"
          align="end"
          sideOffset={10}
        >
          <PopoverHeader>
            <PopoverTitle>Possible causes</PopoverTitle>
            <PopoverDescription>Evidence-linked explanations, updated as the agents work.</PopoverDescription>
          </PopoverHeader>
          <div className="hypothesis-list">
            {hypotheses.map((hypothesis) => (
              <Popover key={hypothesis.id}>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className="hypothesis-item"
                    data-state={hypothesis.state}
                    aria-label={`${hypothesis.label}: ${STATE_LABELS[hypothesis.state]}`}
                  >
                    <span className="hypothesis-marker" aria-hidden="true" />
                    <span className="hypothesis-copy">
                      <strong>{hypothesis.label}</strong>
                      <span>{STATE_LABELS[hypothesis.state]}</span>
                      <small>{hypothesis.evidenceRefs.join(" · ") || "No evidence attached"}</small>
                    </span>
                  </button>
                </PopoverTrigger>
                <PopoverContent className="hypothesis-inspector" side="left" sideOffset={12}>
                  <PopoverHeader>
                    <PopoverTitle>{hypothesis.label}</PopoverTitle>
                    <PopoverDescription>{STATE_LABELS[hypothesis.state]}</PopoverDescription>
                  </PopoverHeader>
                  <p>{hypothesis.note}</p>
                  <div className="evidence-reference-row">
                    {hypothesis.evidenceRefs.length
                      ? hypothesis.evidenceRefs.map((reference) => <code key={reference}>{reference}</code>)
                      : <span>No evidence yet</span>}
                  </div>
                </PopoverContent>
              </Popover>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    </aside>
  )
}
