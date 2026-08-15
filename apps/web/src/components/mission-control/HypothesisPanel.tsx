"use client"

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
    <aside className="hypothesis-rail" aria-labelledby="hypothesis-heading">
      <div className="rail-heading">
        <span>What could cause the dips?</span>
        <h2 id="hypothesis-heading">Possible causes</h2>
      </div>
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
    </aside>
  )
}
