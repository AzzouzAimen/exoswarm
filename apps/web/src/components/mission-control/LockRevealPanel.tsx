"use client"

import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  EyeIcon,
  InformationCircleIcon,
  LockClosedIcon,
} from "@heroicons/react/24/outline"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

import type { DemoCaseDefinition } from "./demo/demo-cases"
import type { InvestigationPresentationState } from "./model/presentation-state"

interface LockRevealPanelProps {
  demoCase: DemoCaseDefinition
  state: InvestigationPresentationState
  revealed: boolean
  onReveal: () => void
  onRestart: () => void
}

export function LockRevealPanel({ demoCase, state, revealed, onReveal, onRestart }: LockRevealPanelProps) {
  const { result, reveal } = demoCase

  const downloadAudit = () => {
    const payload = {
      ...demoCase.auditReport,
      runId: state.run.id,
      terminalReason: result.terminalReason,
      lock: state.lock,
      note: "Presentation fixture export; backend integration pending.",
    }
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
    )
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = result.reportFilename
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="result-panel" aria-labelledby="result-title" aria-live="polite">
      <div className="result-panel-heading">
        <span className="result-icon" data-result={result.kind} aria-hidden="true">
          {result.kind === "locked" ? <CheckCircleIcon /> : <InformationCircleIcon />}
        </span>
        <div>
          <span className="section-kicker">
            {result.kind === "locked" ? "Independent result" : "Safe stop"}
          </span>
          <h2 id="result-title">{result.headline}</h2>
          <p>{result.summary}</p>
        </div>
        <span className="result-disposition" data-result={result.kind}>{result.disposition}</span>
      </div>

      {result.kind === "inconclusive" ? (
        <Alert className="result-alert">
          <InformationCircleIcon aria-hidden="true" />
          <AlertTitle>No catalog comparison opened</AlertTitle>
          <AlertDescription>
            The system made no claim, so it keeps the official identity sealed.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="result-proof">
        <div className="result-reasons">
          <span className="section-kicker">Why it stopped</span>
          <ul>
            {result.reasons.map((reason) => (
              <li key={reason}>
                <CheckCircleIcon aria-hidden="true" /> {reason}
              </li>
            ))}
          </ul>
        </div>

        {result.kind === "locked" && reveal ? (
          <div className="result-comparison" data-revealed={revealed}>
            <div className="result-comparison-heading">
              <div>
                <span className="section-kicker">Official record</span>
                {revealed ? (
                  <>
                    <strong>{reveal.targetName}</strong>
                    <small>{reveal.catalogId} · {reveal.catalogDisposition}</small>
                  </>
                ) : (
                  <>
                    <Skeleton className="h-5 w-40" />
                    <Skeleton className="h-3 w-56" />
                  </>
                )}
              </div>
              {!revealed ? (
                <Button type="button" onClick={onReveal}>
                  <EyeIcon data-icon="inline-start" aria-hidden="true" />
                  Compare with official record
                </Button>
              ) : (
                <span className="comparison-opened">
                  <LockClosedIcon aria-hidden="true" /> Opened after result
                </span>
              )}
            </div>

            {revealed ? (
              <div className="comparison-table" role="table" aria-label="Independent and official results">
                <div role="row" className="comparison-row comparison-header">
                  <span role="columnheader">Measurement</span>
                  <span role="columnheader">ExoSwarm</span>
                  <span role="columnheader">Official</span>
                </div>
                {reveal.comparisonRows.map((row) => (
                  <div role="row" className="comparison-row" key={row.label}>
                    <strong role="cell">{row.label}</strong>
                    <span role="cell">{row.independent}</span>
                    <span role="cell">{row.official}</span>
                  </div>
                ))}
                <small>{reveal.sourceLabel}</small>
              </div>
            ) : (
              <div className="comparison-sealed">
                <LockClosedIcon aria-hidden="true" />
                <span>
                  <strong>Identity stays hidden until you compare</strong>
                  <small>The saved result cannot change after reveal.</small>
                </span>
              </div>
            )}
          </div>
        ) : null}
      </div>

      <div className="result-actions">
        <Button type="button" variant="outline" onClick={downloadAudit}>
          <ArrowDownTrayIcon data-icon="inline-start" aria-hidden="true" />
          Download fixture audit
        </Button>
        <Button type="button" variant="ghost" onClick={onRestart}>
          <ArrowPathIcon data-icon="inline-start" aria-hidden="true" />
          Investigate another target
        </Button>
      </div>

      <Accordion type="single" collapsible className="result-audit">
        <AccordionItem value="audit">
          <AccordionTrigger>Audit details</AccordionTrigger>
          <AccordionContent>
            <dl>
              <div><dt>Run</dt><dd className="telemetry">{state.run.id}</dd></div>
              <div><dt>Stop reason</dt><dd>{result.terminalReason}</dd></div>
              <div><dt>Agent calls</dt><dd>{result.agentCalls}</dd></div>
              <div><dt>Code checks</dt><dd>{result.toolCalls}</dd></div>
              {state.lock ? (
                <>
                  <div><dt>Committed</dt><dd className="telemetry">{state.lock.lockedAt}</dd></div>
                  <div><dt>Receipt</dt><dd className="telemetry">{state.lock.hash}</dd></div>
                </>
              ) : null}
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  )
}
