"use client"

import { Bars3BottomRightIcon } from "@heroicons/react/24/outline"

import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"

import type { InvestigationPresentationState } from "./model/presentation-state"

export function MobileInvestigationSheet({ state }: { state: InvestigationPresentationState }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button type="button" variant="outline" size="icon-sm" className="mobile-sheet-trigger">
          <Bars3BottomRightIcon aria-hidden="true" />
          <span className="sr-only">Open investigation details</span>
        </Button>
      </SheetTrigger>
      <SheetContent className="mobile-investigation-sheet">
        <SheetHeader>
          <SheetTitle>Investigation details</SheetTitle>
          <SheetDescription>
            Current investigation activity and measurements collected so far.
          </SheetDescription>
        </SheetHeader>
        <div className="mobile-sheet-body">
          <section>
            <span className="section-kicker">Current question</span>
            <h3>{state.currentQuestion}</h3>
            <p>{state.activeAgentId ? `${state.agents.find((agent) => agent.id === state.activeAgentId)?.label ?? "Agent"} is working` : "No agent is working now"}</p>
          </section>
          <section>
            <span className="section-kicker">Measurements</span>
            <ul>
              {state.evidence.map((evidence) => (
                <li key={evidence.id}>
                  <strong>{evidence.id}</strong>
                  <span>{evidence.summary}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
