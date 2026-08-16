"use client"

import {
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  InformationCircleIcon,
  XCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import type { ResultComparisonView } from "./view-models"

interface ResultComparisonPanelProps {
  runId: string
  view: ResultComparisonView
  error?: string
  onClose: () => void
  onRestart: () => void
}

const VERDICT_ICON = {
  match: CheckCircleIcon,
  partial: InformationCircleIcon,
  mismatch: XCircleIcon,
  insufficient: ExclamationTriangleIcon,
}

export function ResultComparisonPanel({
  runId,
  view,
  error,
  onClose,
  onRestart,
}: ResultComparisonPanelProps) {
  const VerdictIcon = VERDICT_ICON[view.verdict]
  const downloadAudit = () => {
    const payload = view.source === "live"
      ? { run_id: runId, result: view, artifacts: view.artifacts }
      : { ...view.fixtureAudit, runId, result: view }
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }))
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = view.reportFilename
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
      data-verdict={view.verdict}
      onKeyDown={(event) => { if (event.key === "Escape") onClose() }}
    >
      <Button type="button" variant="ghost" size="icon-sm" className="result-close" aria-label="Close result and return to investigation" onClick={onClose}>
        <XMarkIcon aria-hidden="true" />
      </Button>

      <div className="result-top-actions">
        <Button type="button" onClick={onRestart}><ArrowLeftIcon data-icon="inline-start" aria-hidden="true" />Choose another target</Button>
        <Button type="button" variant="outline" onClick={onClose}><EyeIcon data-icon="inline-start" aria-hidden="true" />Review investigation</Button>
      </div>

      <div className="result-panel-heading">
        <span className="result-icon" data-verdict={view.verdict} aria-hidden="true"><VerdictIcon /></span>
        <div>
          <span className="section-kicker">Independent result vs official catalog</span>
          <h2 id="result-title">{view.headline}</h2>
          <p id="result-summary">{view.summary}</p>
        </div>
        <Badge variant="outline" className="result-verdict" data-verdict={view.verdict}>{view.verdictLabel}</Badge>
      </div>

      <Alert className="result-alert">
        <EyeIcon aria-hidden="true" />
        <AlertTitle>{view.reference.identity} · {view.reference.catalogDisposition}</AlertTitle>
        <AlertDescription>
          This official reference was visible to you throughout the demo. The agents received only the opaque ID and independent evidence.
          {error ? ` ${error}` : ""}
        </AlertDescription>
      </Alert>

      <div className="result-comparison">
        <div className="result-comparison-heading">
          <div>
            <span className="section-kicker">Clear comparison</span>
            <strong>What the agents found vs what is known</strong>
            <small>{view.reference.catalogId} · {view.reference.sourceLabel}</small>
          </div>
          <span className="comparison-viewer-only">Viewer-only reference</span>
        </div>
        <div className="comparison-table" role="table" aria-label="Independent investigation and official catalog comparison">
          <div role="row" className="comparison-row comparison-header">
            <span role="columnheader">Result</span><span role="columnheader">Agents found</span><span role="columnheader">Official catalog</span>
          </div>
          {view.comparisonRows.map((row) => (
            <div role="row" className="comparison-row" key={row.label}>
              <strong role="cell">{row.label}</strong><span role="cell">{row.independent}</span><span role="cell">{row.official}</span>
            </div>
          ))}
        </div>
      </div>

      {(view.source === "fixture" || view.artifacts.length > 0) ? (
        <div className="result-download-action">
          <Button type="button" variant="outline" onClick={downloadAudit}><ArrowDownTrayIcon data-icon="inline-start" aria-hidden="true" />Download details</Button>
        </div>
      ) : null}

      <Accordion type="multiple" className="result-audit">
        <AccordionItem value="evidence">
          <AccordionTrigger>Why the agents reached this result</AccordionTrigger>
          <AccordionContent>
            <ul className="result-detail-list">
              {view.reasons.map((reason) => <li key={reason}><CheckCircleIcon aria-hidden="true" />{reason}</li>)}
            </ul>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="audit">
          <AccordionTrigger>Technical details</AccordionTrigger>
          <AccordionContent>
            <dl>
              <div><dt>Run</dt><dd className="telemetry">{runId}</dd></div>
              <div><dt>Stop reason</dt><dd>{view.terminalReason}</dd></div>
              <div><dt>Agent result</dt><dd>{view.agentDisposition}</dd></div>
              <div><dt>Agent calls</dt><dd>{view.agentCalls}</dd></div>
              <div><dt>Code checks</dt><dd>{view.toolCalls}</dd></div>
              <div><dt>Reference</dt><dd><a href={view.reference.sourceUrl} target="_blank" rel="noreferrer">Open catalog source</a></dd></div>
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  )
}
