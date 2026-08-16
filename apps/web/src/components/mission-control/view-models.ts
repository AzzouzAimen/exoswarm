import type { ArtifactMetadata, MissionControlSnapshot, TargetOption, ViewerTarget } from "@/lib/contracts"

import type { DemoCaseDefinition } from "./demo/demo-cases"

export interface LaunchTargetView {
  id: string
  observationLabel: string
  available: boolean
  officialIdentity?: string
}

export type ComparisonVerdict = "match" | "partial" | "mismatch" | "insufficient"

export interface ViewerReferenceView {
  identity: string
  catalogId: string
  catalogDisposition: string
  sourceLabel: string
  sourceUrl: string
  knownValues: Array<{ label: string; value: string }>
}

export interface ResultComparisonView {
  source: "live" | "fixture"
  status: string
  verdict: ComparisonVerdict
  verdictLabel: string
  headline: string
  summary: string
  agentDisposition: string
  reasons: string[]
  reference: ViewerReferenceView
  comparisonRows: Array<{ label: string; independent: string; official: string }>
  terminalReason: string
  agentCalls: number
  toolCalls: number
  reportFilename: string
  artifacts: ArtifactMetadata[]
  fixtureAudit?: Record<string, unknown>
}

export interface RunIntegrityView {
  agentCalls: number
  toolCalls: number
  provider?: string
  modelIdentity?: string
  rawSamplesSent?: number
}

export const TARGET_PAGE_SIZE = 3

export function targetPageCount(targets: LaunchTargetView[]): number {
  return Math.max(1, Math.ceil(targets.length / TARGET_PAGE_SIZE))
}

export function targetPage(targets: LaunchTargetView[], page: number): LaunchTargetView[] {
  const boundedPage = Math.min(Math.max(0, page), targetPageCount(targets) - 1)
  const start = boundedPage * TARGET_PAGE_SIZE
  return targets.slice(start, start + TARGET_PAGE_SIZE)
}

export function targetPageForSelection(targets: LaunchTargetView[], selectedId: string): number {
  const index = targets.findIndex((target) => target.id === selectedId)
  return index < 0 ? 0 : Math.floor(index / TARGET_PAGE_SIZE)
}

export function launchTargets(
  targets: TargetOption[],
  viewerTargets: ViewerTarget[] = [],
  fixtureCases?: Record<string, DemoCaseDefinition>,
): LaunchTargetView[] {
  const viewerById = new Map(viewerTargets.map((target) => [target.opaque_target_id, target]))
  return targets.map((target) => {
    const fixture = fixtureCases?.[target.opaque_target_id]
    const viewer = viewerById.get(target.opaque_target_id)
    return {
      id: target.opaque_target_id,
      observationLabel: target.sector ? `Cached TESS observation · Sector ${target.sector}` : "Cached TESS observation",
      available: target.cached_lightcurve_available,
      ...(viewer?.target_name || fixture?.reveal?.targetName
        ? { officialIdentity: viewer?.target_name ?? fixture?.reveal?.targetName }
        : {}),
    }
  })
}

const TEST_LABELS: Record<string, string> = {
  signal_quality: "Signal quality and periodicity checked",
  odd_even: "Alternating transit depths compared",
  secondary_eclipse: "Secondary eclipse searched",
  contamination: "Nearby-source contamination screened",
  harmonic_test: "Half- and double-period alternatives tested",
}

const DISPOSITION_LABELS: Record<string, string> = {
  PLANETARY_INTERPRETATION_WEAK: "Planet-like signal; contamination remains unresolved",
  PLANETARY_INTERPRETATION_REJECTED: "Planet interpretation rejected",
  PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING: "Planet-like signal survives implemented vetting",
  TRANSIT_LIKE_SIGNAL: "Transit-like signal",
}

const TERMINAL_REASON_LABELS: Record<string, string> = {
  NO_AVAILABLE_ADAPTIVE_ACTION: "The bounded investigation completed every useful check currently available.",
  "AGENT_STOP:REAL_TESS_BASELINE_COMPLETE": "The required checks are complete and the independent result is ready.",
  "DETERMINISTIC_EVIDENCE:ODD_EVEN_MISMATCH": "Alternating transit depths disagree, which rejects the planet interpretation.",
}

function sentenceLabel(value: string): string {
  const normalized = value.replaceAll("_", " ").replaceAll(":", ": ").toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

function testLabel(value: string): string {
  return TEST_LABELS[value] ?? sentenceLabel(value)
}

function terminalReasonLabel(value: string | null): string {
  if (!value) return "The backend recorded the final investigation state."
  if (TERMINAL_REASON_LABELS[value]) return TERMINAL_REASON_LABELS[value]
  if (value.startsWith("PRECONDITION_FAILED:")) {
    return "The observation did not contain enough reliable signal for candidate-dependent checks."
  }
  return sentenceLabel(value)
}

function dispositionLabel(value: string | null): string {
  if (!value) return "No scientific claim"
  return DISPOSITION_LABELS[value] ?? sentenceLabel(value)
}

function independentMeasurement(
  snapshot: MissionControlSnapshot,
  catalogKey: string,
): string {
  const measurements = snapshot.candidate_signals[0]?.measurements
  if (!measurements) return "Not measured"
  if (catalogKey === "period_days") return measurements.period?.display_value ?? "Not measured"
  if (catalogKey === "duration_hours" || catalogKey === "primary_duration_hours") return measurements.duration?.display_value ?? "Not measured"
  if (catalogKey === "depth_percent" || catalogKey === "primary_depth_percent") {
    const depth = measurements.depth?.value
    return typeof depth === "number" ? `${(depth * 100).toFixed(3)}%` : "Not measured"
  }
  return "Not measured"
}

function catalogValue(label: string, value: number | string): string {
  if (typeof value !== "number") return String(value)
  if (label.endsWith("_days")) return `${value.toFixed(6)} d`
  if (label.endsWith("_hours")) return `${value.toFixed(3)} h`
  if (label.endsWith("_percent")) return `${value.toFixed(3)}%`
  return String(value)
}

function viewerReference(target: ViewerTarget): ViewerReferenceView {
  return {
    identity: target.target_name,
    catalogId: `TIC ${target.tic_id}`,
    catalogDisposition: sentenceLabel(target.catalog_disposition),
    sourceLabel: target.catalog_source,
    sourceUrl: target.catalog_source_url,
    knownValues: Object.entries(target.known_values).map(([label, value]) => ({
      label: sentenceLabel(label),
      value: catalogValue(label, value),
    })),
  }
}

function comparisonVerdict(
  status: string,
  agentDisposition: string | null,
  catalogDisposition: string,
): ComparisonVerdict {
  if (["INSUFFICIENT_EVIDENCE", "FAILED", "BUDGET_EXHAUSTED"].includes(status) || !agentDisposition) return "insufficient"
  const officialPlanet = catalogDisposition.toUpperCase().includes("PLANET")
  const officialBinary = catalogDisposition.toUpperCase().includes("BINARY")
  const agentRejected = agentDisposition === "PLANETARY_INTERPRETATION_REJECTED"
  const agentStrongPlanet = agentDisposition === "PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING"
  const agentWeakPlanet = ["PLANETARY_INTERPRETATION_WEAK", "TRANSIT_LIKE_SIGNAL"].includes(agentDisposition)
  if ((officialPlanet && agentStrongPlanet) || (officialBinary && agentRejected)) return "match"
  if (officialPlanet && agentWeakPlanet) return "partial"
  if ((officialPlanet && agentRejected) || (officialBinary && (agentStrongPlanet || agentWeakPlanet))) return "mismatch"
  return "insufficient"
}

const VERDICT_COPY: Record<ComparisonVerdict, { label: string; headline: string; summary: string }> = {
  match: {
    label: "Match",
    headline: "The agents reached the correct broad conclusion",
    summary: "The independent investigation agrees with the official catalog classification.",
  },
  partial: {
    label: "Partial match",
    headline: "The agents found the signal, but stopped short",
    summary: "The investigation points in the same direction as the catalog, with unresolved caveats.",
  },
  mismatch: {
    label: "Did not match",
    headline: "The agents did not match the catalog result",
    summary: "The independent interpretation conflicts with the official catalog classification.",
  },
  insufficient: {
    label: "Not enough evidence",
    headline: "The agents could not reach a supported conclusion",
    summary: "The run ended without enough evidence to compare a classification.",
  },
}

export function liveResultComparisonView(
  snapshot: MissionControlSnapshot,
  artifacts: ArtifactMetadata[],
  viewerTarget: ViewerTarget,
): ResultComparisonView {
  const verdict = comparisonVerdict(snapshot.status, snapshot.disposition, viewerTarget.catalog_disposition)
  const copy = VERDICT_COPY[verdict]
  const reference = viewerReference(viewerTarget)
  return {
    source: "live",
    status: snapshot.status,
    verdict,
    verdictLabel: copy.label,
    headline: copy.headline,
    summary: copy.summary,
    agentDisposition: dispositionLabel(snapshot.disposition),
    reasons: snapshot.completed_tests.length
      ? snapshot.completed_tests.map(testLabel)
      : [terminalReasonLabel(snapshot.terminal_reason)],
    reference,
    comparisonRows: [
      {
        label: "Interpretation",
        independent: dispositionLabel(snapshot.disposition),
        official: reference.catalogDisposition,
      },
      ...Object.entries(viewerTarget.known_values).map(([label, value]) => ({
        label: sentenceLabel(label),
        independent: independentMeasurement(snapshot, label),
        official: catalogValue(label, value),
      })),
    ],
    terminalReason: terminalReasonLabel(snapshot.terminal_reason),
    agentCalls: snapshot.inference_summary.agent_calls,
    toolCalls: snapshot.budgets.tool_call_count,
    reportFilename: `${snapshot.run_id}-artifact-metadata.json`,
    artifacts,
  }
}

export function fixtureResultComparisonView(
  demoCase: DemoCaseDefinition,
  target: ViewerTarget,
): ResultComparisonView {
  const agentDisposition = demoCase.result.kind === "inconclusive"
    ? null
    : demoCase.result.disposition.toLowerCase().includes("binary")
      ? "PLANETARY_INTERPRETATION_REJECTED"
      : "PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING"
  const verdict = comparisonVerdict(
    demoCase.result.kind === "inconclusive" ? "INSUFFICIENT_EVIDENCE" : "READY_TO_LOCK",
    agentDisposition,
    target.catalog_disposition,
  )
  const copy = VERDICT_COPY[verdict]
  const reference = viewerReference(target)
  return {
    source: "fixture",
    status: demoCase.result.kind === "inconclusive" ? "INSUFFICIENT_EVIDENCE" : "READY_TO_LOCK",
    verdict,
    verdictLabel: copy.label,
    headline: copy.headline,
    summary: copy.summary,
    agentDisposition: demoCase.result.disposition,
    reasons: demoCase.result.reasons,
    reference,
    comparisonRows: demoCase.reveal?.comparisonRows ?? [{
      label: "Interpretation",
      independent: demoCase.result.disposition,
      official: reference.catalogDisposition,
    }],
    terminalReason: demoCase.result.terminalReason,
    agentCalls: demoCase.result.agentCalls,
    toolCalls: demoCase.result.toolCalls,
    reportFilename: demoCase.result.reportFilename,
    artifacts: [],
    fixtureAudit: demoCase.auditReport,
  }
}

export function liveIntegrityView(snapshot: MissionControlSnapshot): RunIntegrityView {
  return {
    agentCalls: snapshot.inference_summary.agent_calls,
    toolCalls: snapshot.budgets.tool_call_count,
    provider: snapshot.inference_summary.provider,
    modelIdentity: snapshot.inference_summary.model_identity,
    rawSamplesSent: snapshot.inference_summary.raw_light_curve_samples_sent,
  }
}
