import {
  DEMO_EVENTS,
  DEMO_INITIAL_STATE,
  DEMO_INSTRUMENTS,
  DEMO_STAGE_MARKERS,
} from "./demo-investigation.fixture"
import type {
  EvidencePresentation,
  InstrumentMode,
  InstrumentPresentation,
  InvestigationPresentationState,
  PresentationEvent,
} from "../model/presentation-state"

export type DemoCaseId = "TARGET-C11" | "TARGET-B42" | "TARGET-D31"

export interface DemoRunResult {
  kind: "locked" | "inconclusive"
  headline: string
  summary: string
  disposition: string
  reasons: string[]
  checksCompleted: number
  agentCalls: number
  toolCalls: number
  terminalReason: string
  reportFilename: string
}

export interface DemoReveal {
  targetName: string
  catalogId: string
  catalogDisposition: string
  sourceLabel: string
  comparisonRows: Array<{ label: string; independent: string; official: string }>
}

export interface DemoCaseDefinition {
  id: DemoCaseId
  sector: string
  initialState: InvestigationPresentationState
  events: PresentationEvent[]
  instruments: Record<InstrumentMode, InstrumentPresentation>
  stageMarkers: ReadonlyArray<{ label: string; step: number }>
  result: DemoRunResult
  reveal?: DemoReveal
  auditReport: Record<string, unknown>
}

const agents = DEMO_INITIAL_STATE.agents.map((agent) => ({
  ...agent,
  status: agent.id === "observer" ? ("complete" as const) : ("waiting" as const),
  summary: agent.id === "observer" ? "Cached observation checked" : "Idle",
}))

function evidence(
  id: string,
  kind: string,
  sourceTool: string,
  summary: string,
  supports: string[],
  contradicts: string[],
): EvidencePresentation {
  return {
    id,
    kind,
    sourceTool,
    summary,
    supports,
    contradicts,
    provenance: `fixture://cached-backend/${id}`,
  }
}

function summaryInstrument(
  mode: InstrumentMode,
  label: string,
  annotation: string,
  x: number[],
  y: number[],
  readouts: InstrumentPresentation["readouts"],
): InstrumentPresentation {
  return {
    mode,
    label,
    available: true,
    plot: {
      traces: [{ name: label, x, y, kind: mode === "raw" ? "markers" : "bar", tone: "science" }],
      xLabel: mode === "raw" ? "Display sample" : "Check",
      yLabel: mode === "raw" ? "Normalized brightness" : "Measured value",
      annotation,
    },
    readouts,
  }
}

const b42RawX = Array.from({ length: 48 }, (_, index) => index)
const b42RawY = b42RawX.map((index) =>
  index % 13 < 2 ? 0.8779 : index % 7 === 0 ? 0.9114 : 1 + Math.sin(index * 0.7) * 0.002,
)
const b42OddEven = summaryInstrument(
  "odd-even",
  "Alternating-event check",
  "Alternating events have very different depths—a strong binary warning.",
  [1, 2],
  [14.705, 8.856],
  [
    { label: "First set", value: "14.705 %", evidenceRef: "B18" },
    { label: "Second set", value: "8.856 %", evidenceRef: "B18" },
    { label: "Difference", value: "37.62 σ", evidenceRef: "B18" },
  ],
)
const b42Instruments: Record<InstrumentMode, InstrumentPresentation> = {
  ...DEMO_INSTRUMENTS,
  raw: summaryInstrument(
    "raw",
    "Brightness over time",
    "A display sample of the cached observation; measurements come from deterministic code.",
    b42RawX,
    b42RawY,
    [
      { label: "Source", value: "cached TESS fixture" },
      { label: "Sector", value: "5" },
    ],
  ),
  bls: summaryInstrument(
    "bls",
    "Repeat-pattern search",
    "Code found a strong repeating event.",
    [0.347, 0.695, 1.39],
    [3.2, 12.4, 7.8],
    [
      { label: "Repeats every", value: "0.694807 days", evidenceRef: "B14" },
      { label: "Signal-to-noise", value: "6668.3", evidenceRef: "B14" },
    ],
  ),
  "phase-fold": summaryInstrument(
    "phase-fold",
    "Events lined up",
    "The repeating dimming is deep enough to demand a stellar-binary check.",
    [-0.1, 0, 0.1],
    [1, 0.8779, 1],
    [
      { label: "Brightness drop", value: "12.21 %", evidenceRef: "B14" },
      { label: "Duration", value: "3.0 h", evidenceRef: "B14" },
    ],
  ),
  "odd-even": b42OddEven,
  secondary: b42OddEven,
  harmonic: b42OddEven,
}

const d31RawX = Array.from({ length: 48 }, (_, index) => index)
const d31RawY = d31RawX.map((index) => 1 + Math.sin(index * 0.71) * 0.0012 + Math.cos(index * 0.19) * 0.0008)
const d31Raw = summaryInstrument(
  "raw",
  "Brightness over time",
  "The cached observation is usable, but no stable repeat clears the evidence threshold.",
  d31RawX,
  d31RawY,
  [
    { label: "Source", value: "cached TESS fixture" },
    { label: "Search result", value: "no stable repeat" },
  ],
)
const d31Instruments = Object.fromEntries(
  (Object.keys(DEMO_INSTRUMENTS) as InstrumentMode[]).map((mode) => [mode, { ...d31Raw, mode }]),
) as Record<InstrumentMode, InstrumentPresentation>

const B14 = evidence(
  "B14",
  "candidate-period",
  "search_bls",
  "Code found a deep repeating event every 0.694807 days.",
  ["planetary-transit", "eclipsing-binary"],
  ["instrument-artifact"],
)
const B18 = evidence(
  "B18",
  "odd-even-diagnostic",
  "odd_even",
  "Alternating event depths differ by 37.62 sigma.",
  ["eclipsing-binary"],
  ["planetary-transit"],
)

const baseState = (
  id: DemoCaseId,
  sector: string,
  instrument: InstrumentPresentation,
): InvestigationPresentationState => ({
  ...DEMO_INITIAL_STATE,
  run: { id: `fixture_run_${id.slice(-3)}`, mode: "fixture" },
  target: {
    id,
    sector: `Sector ${sector}`,
    dataLabel: "Cached TESS presentation fixture",
    groundTruthState: "sealed",
  },
  agents,
  instrument,
  evidence: [
    {
      ...DEMO_INITIAL_STATE.evidence[0],
      id: `${id.slice(-3)}11`,
      provenance: `fixture://cached-backend/${id}/preprocess-v1`,
    },
  ],
  hypotheses: DEMO_INITIAL_STATE.hypotheses.map((hypothesis) => ({
    ...hypothesis,
    evidenceRefs: [],
    state: "unresolved" as const,
  })),
  timeline: [],
  lock: undefined,
})

const bt = (seconds: number) => `20:52:${String(seconds).padStart(2, "0")}`
const B42_EVENTS: PresentationEvent[] = [
  {
    eventId: "b42-01", type: "agent.started", agentId: "signal", timestamp: bt(2), holdMs: 1800,
    trace: { actor: "SIGNAL", headline: "Repeat search selected", detail: "Look for stable timing before classifying", tone: "model" },
  },
  {
    eventId: "b42-02", type: "tool.started", tool: { name: "search_bls", status: "running", authority: "deterministic" }, budgetUsed: 0, timestamp: bt(4), holdMs: 1500,
    trace: { actor: "SCIENCE TOOL", headline: "Repeat-pattern search running", detail: "Deterministic scan", tone: "science" },
  },
  {
    eventId: "b42-03", type: "tool.completed", tool: { name: "search_bls", status: "complete", durationMs: 964, authority: "deterministic", evidenceRef: "B14" }, timestamp: bt(6), holdMs: 1900,
    view: { phase: "candidate", stageIndex: 2, stageLabel: "Repeat found", currentQuestion: "What could cause this deep repeat?", cameraPose: "candidate", instrument: b42Instruments.bls },
    trace: { actor: "SCIENCE TOOL", headline: "Repeat found", detail: "0.694807 d · 12.21% depth", tone: "science", evidenceRef: "B14" },
  },
  {
    eventId: "b42-04", type: "evidence.appended", evidence: B14, timestamp: bt(8), holdMs: 1500,
    trace: { actor: "EVIDENCE", headline: "Candidate measurements saved", detail: "B14 appended", tone: "science", evidenceRef: "B14" },
  },
  {
    eventId: "b42-05", type: "agent.started", agentId: "skeptic", timestamp: bt(10), holdMs: 1900,
    view: { phase: "challenging", stageIndex: 4, stageLabel: "Challenge signal", currentQuestion: "Do alternating events look different?", cameraPose: "alternatives" },
    trace: { actor: "SKEPTIC", headline: "Binary explanation prioritized", detail: "Deep events require an alternating-event check", tone: "model" },
  },
  {
    eventId: "b42-06", type: "agent.decision", agentId: "skeptic", timestamp: bt(12), holdMs: 1700,
    update: { summary: "Testing alternating event depths" },
    trace: { actor: "SKEPTIC", headline: "Alternating-event check proposed", detail: "Bounded diagnostic · cost 1", tone: "model" },
  },
  {
    eventId: "b42-07", type: "agent.handoff", from: "skeptic", to: "critic", kind: "model", timestamp: bt(14), holdMs: 1000,
    trace: { actor: "HANDOFF", headline: "Skeptic → Critic", detail: "Independent experiment review", tone: "model" },
  },
  {
    eventId: "b42-08", type: "critic.review", verdict: "APPROVE", summary: "The check directly separates the leading explanations.", timestamp: bt(15), holdMs: 1600,
    trace: { actor: "CRITIC", headline: "APPROVE", detail: "Allowlisted · budget valid", tone: "approved" },
  },
  {
    eventId: "b42-09", type: "tool.started", tool: { name: "odd_even", status: "running", authority: "deterministic" }, budgetUsed: 1, timestamp: bt(17), holdMs: 1500,
    view: { phase: "testing", stageIndex: 6, stageLabel: "Run check", currentQuestion: "Are alternating events equally deep?" },
    trace: { actor: "SCIENCE TOOL", headline: "Alternating-event check running", detail: "Code measures both event sets", tone: "science" },
  },
  {
    eventId: "b42-10", type: "tool.completed", tool: { name: "odd_even", status: "complete", durationMs: 318, authority: "deterministic", evidenceRef: "B18" }, timestamp: bt(19), holdMs: 1900,
    view: { instrument: b42OddEven },
    trace: { actor: "SCIENCE TOOL", headline: "Large mismatch measured", detail: "37.62 σ difference", tone: "science", evidenceRef: "B18" },
  },
  {
    eventId: "b42-11", type: "evidence.appended", evidence: B18, timestamp: bt(21), holdMs: 1500,
    trace: { actor: "EVIDENCE", headline: "Binary warning saved", detail: "B18 appended", tone: "science", evidenceRef: "B18" },
  },
  {
    eventId: "b42-12", type: "hypothesis.updated", hypothesisId: "eclipsing-binary", update: { state: "supported", evidenceRefs: ["B14", "B18"], note: "Alternating depths strongly differ" }, timestamp: bt(23), holdMs: 1400,
    trace: { actor: "LEDGER", headline: "Binary explanation supported", detail: "+B14 · +B18", tone: "science" },
  },
  {
    eventId: "b42-13", type: "agent.started", agentId: "director", timestamp: bt(25), holdMs: 1700,
    view: { phase: "locking", stageIndex: 8, stageLabel: "Save result", currentQuestion: "Has the planet-like interpretation failed?", cameraPose: "lock" },
    trace: { actor: "DIRECTOR", headline: "Rejection threshold reached", detail: "Planet-like interpretation does not survive", tone: "model" },
  },
  {
    eventId: "b42-14", type: "result.locked", hash: "35d4d4f5681fe33d90c688a1ad43c759862c965c7447e10b7e0dd4080967510e", lockedAt: "2026-08-15T20:52:27Z", timestamp: bt(27), holdMs: 2500,
    view: { phase: "locked", stageIndex: 9, stageLabel: "Result saved", currentQuestion: "Result saved", cameraPose: "lock" },
    trace: { actor: "AUTHORITY", headline: "Independent result saved", detail: "Committed before the official record is opened", tone: "unresolved" },
  },
]

const dt = (seconds: number) => `21:03:${String(seconds).padStart(2, "0")}`
const D31_EVENTS: PresentationEvent[] = [
  {
    eventId: "d31-01", type: "agent.started", agentId: "signal", timestamp: dt(2), holdMs: 1800,
    trace: { actor: "SIGNAL", headline: "Repeat search selected", detail: "Search the usable observation", tone: "model" },
  },
  {
    eventId: "d31-02", type: "tool.started", tool: { name: "search_bls", status: "running", authority: "deterministic" }, budgetUsed: 0, timestamp: dt(4), holdMs: 1600,
    trace: { actor: "SCIENCE TOOL", headline: "Repeat-pattern search running", detail: "Deterministic scan", tone: "science" },
  },
  {
    eventId: "d31-03", type: "tool.completed", tool: { name: "search_bls", status: "complete", durationMs: 731, authority: "deterministic" }, timestamp: dt(6), holdMs: 1900,
    view: { phase: "challenging", stageIndex: 3, stageLabel: "Check threshold", currentQuestion: "Is any repeat strong enough to investigate?", cameraPose: "alternatives", instrument: d31Raw },
    trace: { actor: "SCIENCE TOOL", headline: "No stable repeat found", detail: "Search completed without qualifying evidence", tone: "science" },
  },
  {
    eventId: "d31-04", type: "agent.decision", agentId: "signal", timestamp: dt(8), holdMs: 1700,
    update: { summary: "No candidate cleared the evidence threshold" },
    trace: { actor: "SIGNAL", headline: "No follow-up check justified", detail: "A weak candidate would waste the evidence budget", tone: "model" },
  },
  {
    eventId: "d31-05", type: "agent.started", agentId: "director", timestamp: dt(10), holdMs: 1800,
    view: { phase: "locking", stageIndex: 5, stageLabel: "Stop safely", currentQuestion: "Should the run stop without a claim?", cameraPose: "lock" },
    trace: { actor: "DIRECTOR", headline: "Evidence remains insufficient", detail: "Stop rule reached without a classification", tone: "model" },
  },
  {
    eventId: "d31-06", type: "run.concluded", timestamp: dt(12), holdMs: 2300,
    view: { stageIndex: 6, stageLabel: "Run concluded", currentQuestion: "No claim made" },
    trace: { actor: "AUTHORITY", headline: "Run closed without a claim", detail: "Insufficient evidence is an allowed outcome", tone: "unresolved" },
  },
]

const C11_RESULT: DemoRunResult = {
  kind: "locked",
  headline: "Planet-like signal survives the checks",
  summary: "The repeating dip stayed consistent while the tested alternatives weakened.",
  disposition: "Candidate survives implemented vetting",
  reasons: ["1.338249-day repeat", "2.30% consistent dip", "No stronger half/double-period explanation"],
  checksCompleted: 4,
  agentCalls: 2,
  toolCalls: 4,
  terminalReason: "Evidence threshold reached",
  reportFilename: "exoswarm-target-c11-audit.json",
}

const C11_REVEAL: DemoReveal = {
  targetName: "WASP-4 b",
  catalogId: "TIC 402026209",
  catalogDisposition: "Confirmed planet",
  sourceLabel: "NASA Exoplanet Archive / cached challenge record",
  comparisonRows: [
    { label: "Period", independent: "1.338249 d", official: "1.338231 d" },
    { label: "Transit depth", independent: "2.305 %", official: "2.312 %" },
    { label: "Interpretation", independent: "Planet-like survives", official: "Confirmed planet" },
  ],
}

export const DEMO_CASES: Record<DemoCaseId, DemoCaseDefinition> = {
  "TARGET-C11": {
    id: "TARGET-C11",
    sector: "2",
    initialState: DEMO_INITIAL_STATE,
    events: DEMO_EVENTS,
    instruments: DEMO_INSTRUMENTS,
    stageMarkers: DEMO_STAGE_MARKERS,
    result: C11_RESULT,
    reveal: C11_REVEAL,
    auditReport: { fixture: true, target: "TARGET-C11", result: C11_RESULT, comparison: C11_REVEAL },
  },
  "TARGET-B42": {
    id: "TARGET-B42",
    sector: "5",
    initialState: baseState("TARGET-B42", "5", b42Instruments.raw),
    events: B42_EVENTS,
    instruments: b42Instruments,
    stageMarkers: [
      { label: "Observe", step: 0 }, { label: "Detect", step: 3 }, { label: "Challenge", step: 6 }, { label: "Measure", step: 10 }, { label: "Save", step: 14 },
    ],
    result: {
      kind: "locked",
      headline: "Planet-like interpretation rejected",
      summary: "Alternating events differ too strongly to behave like one consistent planetary transit.",
      disposition: "Likely eclipsing binary",
      reasons: ["12.21% deep repeating events", "Alternating depths differ by 37.62 σ", "Binary explanation strengthened"],
      checksCompleted: 2,
      agentCalls: 0,
      toolCalls: 2,
      terminalReason: "Rejection threshold reached",
      reportFilename: "exoswarm-target-b42-audit.json",
    },
    reveal: {
      targetName: "TESS-EB TIC 289801742",
      catalogId: "TIC 289801742",
      catalogDisposition: "Eclipsing binary",
      sourceLabel: "TESS eclipsing-binary catalog / cached challenge record",
      comparisonRows: [
        { label: "Detected interval", independent: "0.694807 d", official: "1.389627 d orbit" },
        { label: "Alternating depths", independent: "14.705 / 8.856 %", official: "15.013 / 7.691 %" },
        { label: "Interpretation", independent: "Likely binary", official: "Eclipsing binary" },
      ],
    },
    auditReport: { fixture: true, target: "TARGET-B42", result: "planetary interpretation rejected", oddEvenSigma: 37.62164223683786 },
  },
  "TARGET-D31": {
    id: "TARGET-D31",
    sector: "3",
    initialState: baseState("TARGET-D31", "3", d31Raw),
    events: D31_EVENTS,
    instruments: d31Instruments,
    stageMarkers: [
      { label: "Observe", step: 0 }, { label: "Search", step: 2 }, { label: "Assess", step: 4 }, { label: "Stop", step: 6 },
    ],
    result: {
      kind: "inconclusive",
      headline: "Not enough evidence to decide",
      summary: "No stable repeat cleared the threshold, so the run stopped without making a scientific claim.",
      disposition: "Inconclusive",
      reasons: ["Observation passed basic quality checks", "No repeat cleared the search threshold", "No follow-up experiment was justified"],
      checksCompleted: 1,
      agentCalls: 0,
      toolCalls: 1,
      terminalReason: "Insufficient evidence",
      reportFilename: "exoswarm-target-d31-audit.json",
    },
    reveal: {
      targetName: "TOI-270 b",
      catalogId: "TIC 259377017",
      catalogDisposition: "Confirmed planet",
      sourceLabel: "NASA Exoplanet Archive / cached challenge record",
      comparisonRows: [
        { label: "Search result", independent: "No stable repeat found", official: "3.359920 d period" },
        { label: "Signal depth", independent: "Below search threshold", official: "0.0977 % transit depth" },
        { label: "Interpretation", independent: "Inconclusive", official: "Confirmed planet" },
      ],
    },
    auditReport: { fixture: true, target: "TARGET-D31", result: "insufficient evidence", claimMade: false },
  },
}

export const DEMO_CASE_LIST = Object.values(DEMO_CASES)
