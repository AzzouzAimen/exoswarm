"use client"

import {
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

import type { DemoCaseDefinition } from "./demo/demo-cases"
import type { InvestigationPresentationState } from "./model/presentation-state"

interface LockRevealPanelProps {
  demoCase: DemoCaseDefinition
  state: InvestigationPresentationState
  onClose: () => void
  onRestart: () => void
}

export function LockRevealPanel({ demoCase, state, onClose, onRestart }: LockRevealPanelProps) {
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
    <section
      className="result-panel"
      role="dialog"
      aria-labelledby="result-title"
      aria-describedby="result-summary"
      aria-live="polite"
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose()
      }}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="result-close"
        aria-label="Close result and return to investigation"
        onClick={onClose}
      >
        <XMarkIcon aria-hidden="true" />
      </Button>
      <div className="result-panel-heading">
        <span className="result-icon" data-result={result.kind} aria-hidden="true">
          {result.kind === "locked" ? <CheckCircleIcon /> : <InformationCircleIcon />}
        </span>
        <div>
          <span className="section-kicker">
            {result.kind === "locked" ? "Independent result" : "Safe stop"}
          </span>
          <h2 id="result-title">{result.headline}</h2>
          <p id="result-summary">{result.summary}</p>
        </div>
        <span className="result-disposition" data-result={result.kind}>{result.disposition}</span>
      </div>

      <Alert className="result-alert">
        <InformationCircleIcon aria-hidden="true" />
        <AlertTitle>Official identity is viewer-only</AlertTitle>
        <AlertDescription>
          You can see the catalog record throughout the demo. The agents investigate only the opaque
          target ID and cannot use the official identity or answer.
        </AlertDescription>
      </Alert>

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

        {reveal ? (
          <div className="result-comparison">
            <div className="result-comparison-heading">
              <div>
                <span className="section-kicker">Official catalog record</span>
                <strong>{reveal.targetName}</strong>
                <small>{reveal.catalogId} · {reveal.catalogDisposition}</small>
              </div>
              <span className="comparison-viewer-only">Visible to viewer, hidden from agents</span>
            </div>

            <div className="comparison-table" role="table" aria-label="Agent investigation and official catalog comparison">
              <div role="row" className="comparison-row comparison-header">
                <span role="columnheader">Measurement</span>
                <span role="columnheader">Agent investigation</span>
                <span role="columnheader">Official catalog</span>
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
          </div>
        ) : null}
      </div>

      <div className="result-actions">
        <Button type="button" onClick={onClose}>
          <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" />
          Back to investigation
        </Button>
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
