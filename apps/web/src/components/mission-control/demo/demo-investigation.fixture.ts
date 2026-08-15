import type {
  AgentPresentation,
  EvidencePresentation,
  InstrumentMode,
  InstrumentPresentation,
  InvestigationPresentationState,
  PlotPresentation,
  PresentationEvent,
} from "../model/presentation-state"

/**
 * SYNTHETIC UI DEMO DATA — NOT PRODUCTION SCIENTIFIC DATA.
 *
 * Values in this file exist only to exercise the presentation layer. They are
 * intentionally isolated so a future backend adapter can replace this event
 * source without changing visual components.
 */

const periodDays = 3.184
const transitDepth = 0.0082

function sequence(length: number, start: number, step: number) {
  return Array.from({ length }, (_, index) => start + index * step)
}

const rawTime = sequence(220, 0, 0.1)
const rawFlux = rawTime.map((time, index) => {
  const phase = ((time + periodDays / 2) % periodDays) - periodDays / 2
  const dip = Math.abs(phase) < 0.075 ? transitDepth : 0
  return 1 + Math.sin(index * 0.43) * 0.00055 + Math.sin(index * 0.097) * 0.00035 - dip
})

const blsPeriods = sequence(180, 0.5, 0.035)
const blsPower = blsPeriods.map((value) => {
  const primary = 10.8 * Math.exp(-Math.pow((value - periodDays) / 0.075, 2))
  const alias = 3.1 * Math.exp(-Math.pow((value - periodDays / 2) / 0.11, 2))
  return 0.8 + primary + alias + 0.18 * Math.sin(value * 8)
})

const phase = sequence(180, -0.5, 1 / 179)
const foldedFlux = phase.map(
  (value, index) =>
    1 - transitDepth * Math.exp(-Math.pow(value / 0.035, 6)) + Math.sin(index * 0.71) * 0.00028,
)

const diagnosticPeriod = [periodDays / 2, periodDays, periodDays * 2]
const harmonicPower = [4.2, 11.6, 6.1]

const oddPhase = phase
const oddFlux = phase.map((value) => 1 - 0.0081 * Math.exp(-Math.pow(value / 0.036, 6)))
const evenFlux = phase.map((value) => 1 - 0.0083 * Math.exp(-Math.pow(value / 0.036, 6)))

const secondaryPhase = sequence(160, 0, 1 / 159)
const secondaryFlux = secondaryPhase.map(
  (value) => 1 - 0.00032 * Math.exp(-Math.pow((value - 0.5) / 0.045, 6)),
)

const PLOTS: Record<InstrumentMode, PlotPresentation> = {
  raw: {
    traces: [{ name: "normalized flux", x: rawTime, y: rawFlux, kind: "markers", tone: "muted" }],
    xLabel: "Time · demo days",
    yLabel: "Brightness",
    annotation: "Each dot is one brightness measurement.",
  },
  bls: {
    traces: [{ name: "BLS power", x: blsPeriods, y: blsPower, kind: "line", tone: "science" }],
    xLabel: "Possible repeat interval · days",
    yLabel: "Match strength",
    annotation: "One repeat interval stands out.",
  },
  "phase-fold": {
    traces: [{ name: "phase-folded flux", x: phase, y: foldedFlux, kind: "markers", tone: "science" }],
    xLabel: "Position in one orbit",
    yLabel: "Brightness",
    annotation: "Repeated dips stacked onto one orbit.",
  },
  "odd-even": {
    traces: [
      { name: "odd", x: oddPhase, y: oddFlux, kind: "line", tone: "science" },
      { name: "even", x: oddPhase, y: evenFlux, kind: "line", tone: "unresolved", dash: "dash" },
    ],
    xLabel: "Position in one orbit",
    yLabel: "Brightness",
    annotation: "Alternating dips have nearly the same depth.",
  },
  secondary: {
    traces: [{ name: "secondary scan", x: secondaryPhase, y: secondaryFlux, kind: "line", tone: "muted" }],
    xLabel: "Position in one orbit",
    yLabel: "Brightness change",
    annotation: "No second eclipse stands out.",
  },
  harmonic: {
    traces: [{ name: "relative support", x: diagnosticPeriod, y: harmonicPower, kind: "bar", tone: "science" }],
    xLabel: "Period checked · days",
    yLabel: "Match strength",
    annotation: "Half and double periods fit less well.",
  },
}

function instrument(
  mode: InstrumentMode,
  label: string,
  readouts: InstrumentPresentation["readouts"],
): InstrumentPresentation {
  return { mode, label, plot: PLOTS[mode], readouts }
}

export const DEMO_INSTRUMENTS: Record<InstrumentMode, InstrumentPresentation> = {
  raw: instrument("raw", "Brightness over time", [
    { label: "Readings", value: "220 demo points", evidenceRef: "E11" },
    { label: "Data", value: "synthetic demo" },
  ]),
  bls: instrument("bls", "Period search", [
    { label: "Repeats every", value: "3.184 days", evidenceRef: "E14" },
    { label: "Method", value: "period search" },
  ]),
  "phase-fold": instrument("phase-fold", "Dips lined up", [
    { label: "Repeats every", value: "3.184 days", evidenceRef: "E14" },
    { label: "Brightness drop", value: "0.82 %", evidenceRef: "E17" },
  ]),
  "odd-even": instrument("odd-even", "Alternating dip check", [
    { label: "First set", value: "0.81 %" },
    { label: "Second set", value: "0.83 %" },
    { label: "Data", value: "synthetic demo" },
  ]),
  secondary: instrument("secondary", "Hidden companion check", [
    { label: "Checked near", value: "half an orbit" },
    { label: "Result", value: "no clear second dip" },
  ]),
  harmonic: instrument("harmonic", "Alternative periods", [
    { label: "P/2", value: "1.592 d" },
    { label: "P", value: "3.184 d", evidenceRef: "E14" },
    { label: "2P", value: "6.368 d" },
  ]),
}

const agents: AgentPresentation[] = [
  ["director", "Director", "Plans the next check"],
  ["observer", "Observer", "Checks data quality"],
  ["signal", "Signal", "Finds repeats"],
  ["transit_hunter", "Transit", "Measures the dips"],
  ["skeptic", "Skeptic", "Tests other causes"],
  ["critic", "Critic", "Approves safe checks"],
].map(([id, label, role]) => ({
  id: id as AgentPresentation["id"],
  label,
  function: role,
  status: id === "observer" ? "complete" : "waiting",
  summary: id === "observer" ? "Demo data quality checked" : "Idle",
  inspector: {
    currentQuestion: "No active question",
    evidenceRefs: id === "observer" ? ["E11"] : [],
    action: "none",
    expectedDiscriminator: "not selected",
    model: id === "critic" || id === "skeptic" ? "DeepSeek-V4 · demo trace" : "Scripted demo role",
    latency: "not measured",
    schema: "scripted",
  },
}))

export const DEMO_EVIDENCE: Record<string, EvidencePresentation> = {
  E11: {
    id: "E11",
    kind: "observation-quality",
    sourceTool: "preprocess",
    summary: "The time coverage is good enough to search for repeats.",
    supports: [],
    contradicts: ["instrument-artifact"],
    provenance: "synthetic://demo/preprocess-v1",
  },
  E14: {
    id: "E14",
    kind: "candidate-period",
    sourceTool: "search_bls",
    summary: "A repeating dip appears every 3.184 days.",
    measurement: { value: periodDays, displayValue: "3.184", unit: "d" },
    supports: ["planetary-transit", "eclipsing-binary"],
    contradicts: ["instrument-artifact"],
    provenance: "synthetic://demo/search_bls-v1",
  },
  E17: {
    id: "E17",
    kind: "phase-consistency",
    sourceTool: "measure_transit",
    summary: "The dips line up when each 3.184-day cycle is stacked.",
    measurement: { value: transitDepth, displayValue: "0.82", unit: "% depth" },
    supports: ["planetary-transit", "eclipsing-binary"],
    contradicts: ["instrument-artifact"],
    provenance: "synthetic://demo/measure_transit-v1",
  },
  E18: {
    id: "E18",
    kind: "harmonic-diagnostic",
    sourceTool: "harmonic_test",
    summary: "Half and double periods fit worse than 3.184 days.",
    supports: ["planetary-transit"],
    contradicts: ["eclipsing-binary"],
    provenance: "synthetic://demo/harmonic_test-v1",
  },
}

export const DEMO_INITIAL_STATE: InvestigationPresentationState = {
  run: { id: "demo_run_7A21", mode: "demo" },
  target: {
    id: "TARGET-DEMO-07",
    sector: "Sector 21",
    dataLabel: "Synthetic demo data",
    groundTruthState: "sealed",
  },
  phase: "observing",
  stageIndex: 1,
  stageLabel: "Observe",
  currentQuestion: "Do the brightness dips repeat?",
  agents,
  hypotheses: [
    {
      id: "planetary-transit",
      label: "Planet crossing",
      state: "unresolved",
      evidenceRefs: [],
      note: "No orbit has been measured yet.",
    },
    {
      id: "eclipsing-binary",
      label: "Two stars eclipsing",
      state: "unresolved",
      evidenceRefs: [],
      note: "A second star could create similar dips.",
    },
    {
      id: "instrument-artifact",
      label: "Instrument noise",
      state: "unresolved",
      evidenceRefs: ["E11"],
      note: "The first data-quality check passed.",
    },
  ],
  evidence: [DEMO_EVIDENCE.E11],
  instrument: DEMO_INSTRUMENTS.raw,
  evidenceBudget: { used: 0, total: 4 },
  cameraPose: "field",
  timeline: [],
}

const t = (seconds: number) => `20:41:${String(seconds).padStart(2, "0")}`

export const DEMO_EVENTS: PresentationEvent[] = [
  {
    eventId: "evt-01",
    type: "agent.started",
    agentId: "signal",
    timestamp: t(2),
    holdMs: 2200,
    trace: {
      actor: "SIGNAL",
      headline: "Periodic search selected",
      detail: "Search before inferring geometry",
      tone: "model",
    },
  },
  {
    eventId: "evt-02",
    type: "tool.started",
    tool: { name: "search_bls", status: "running", authority: "deterministic" },
    budgetUsed: 0,
    timestamp: t(4),
    holdMs: 1800,
    trace: {
      actor: "SCIENCE TOOL",
      headline: "BLS search running",
      detail: "Deterministic period scan",
      tone: "science",
    },
  },
  {
    eventId: "evt-03",
    type: "tool.completed",
    tool: { name: "search_bls", status: "complete", durationMs: 1180, authority: "deterministic" },
    timestamp: t(6),
    holdMs: 2200,
    view: {
      phase: "candidate",
      stageIndex: 2,
      stageLabel: "Repeat found",
      currentQuestion: "What orbit matches this repeat?",
      cameraPose: "candidate",
      instrument: instrument("bls", "Period search", [
        { label: "Repeats every", value: "3.184 days", evidenceRef: "E14" },
        { label: "Method", value: "period search" },
      ]),
    },
    trace: {
      actor: "SCIENCE TOOL",
      headline: "BLS search complete",
      detail: "1.18 s · candidate period returned",
      tone: "science",
    },
  },
  {
    eventId: "evt-04",
    type: "evidence.appended",
    evidence: DEMO_EVIDENCE.E14,
    timestamp: t(7),
    holdMs: 2100,
    trace: {
      actor: "EVIDENCE",
      headline: "E14 appended",
      detail: "Candidate period · 3.184 d",
      tone: "science",
      evidenceRef: "E14",
    },
  },
  {
    eventId: "evt-05",
    type: "hypothesis.updated",
    hypothesisId: "planetary-transit",
    update: { state: "supported", evidenceRefs: ["E14"], note: "Provisional geometry only" },
    timestamp: t(9),
    holdMs: 1900,
    trace: {
      actor: "LEDGER",
      headline: "Hypothesis updated",
      detail: "Planetary transit +E14 · provisional",
      tone: "science",
    },
  },
  {
    eventId: "evt-06",
    type: "agent.started",
    agentId: "transit_hunter",
    timestamp: t(11),
    holdMs: 2300,
    view: {
      phase: "characterizing",
      stageIndex: 3,
      stageLabel: "Line up dips",
      currentQuestion: "Do the dips line up each orbit?",
      cameraPose: "transit",
      instrument: instrument("phase-fold", "Dips lined up", [
        { label: "Center", value: "mid-dip" },
        { label: "Repeats every", value: "3.184 days", evidenceRef: "E14" },
      ]),
    },
    trace: {
      actor: "TRANSIT",
      headline: "Transit geometry under review",
      detail: "Phase alignment is now the focus",
      tone: "model",
    },
  },
  {
    eventId: "evt-07",
    type: "evidence.appended",
    evidence: DEMO_EVIDENCE.E17,
    timestamp: t(14),
    holdMs: 2400,
    view: {
      phase: "measuring",
      stageIndex: 4,
      stageLabel: "Measure signal",
      currentQuestion: "How deep is the repeating dip?",
      cameraPose: "measurement",
      instrument: instrument("phase-fold", "Dips lined up", [
        { label: "Repeats every", value: "3.184 days", evidenceRef: "E14" },
        { label: "Brightness drop", value: "0.82 %", evidenceRef: "E17" },
        { label: "View", value: "illustration" },
      ]),
    },
    trace: {
      actor: "EVIDENCE",
      headline: "E17 appended",
      detail: "Phase-consistent depth · 0.82 %",
      tone: "science",
      evidenceRef: "E17",
    },
  },
  {
    eventId: "evt-08",
    type: "hypothesis.updated",
    hypothesisId: "planetary-transit",
    update: { state: "supported", evidenceRefs: ["E14", "E17"], note: "Survives measured phase check" },
    timestamp: t(17),
    holdMs: 1600,
    trace: {
      actor: "LEDGER",
      headline: "Leading interpretation strengthened",
      detail: "Supported by E14 · E17",
      tone: "science",
    },
  },
  {
    eventId: "evt-09",
    type: "hypothesis.updated",
    hypothesisId: "instrument-artifact",
    update: { state: "weakened", evidenceRefs: ["E11", "E17"], note: "Repeatable phase structure" },
    timestamp: t(18),
    holdMs: 1700,
    trace: {
      actor: "LEDGER",
      headline: "Instrument artifact weakened",
      detail: "−E11 · −E17",
      tone: "science",
    },
  },
  {
    eventId: "evt-10",
    type: "agent.started",
    agentId: "skeptic",
    timestamp: t(20),
    holdMs: 2400,
    view: {
      phase: "challenging",
      stageIndex: 5,
      stageLabel: "Test another cause",
      currentQuestion: "Could two stars explain the dips instead?",
      cameraPose: "alternatives",
    },
    trace: {
      actor: "SKEPTIC",
      headline: "Alternative selected",
      detail: "Test P/2, P and 2P consistency",
      tone: "unresolved",
    },
  },
  {
    eventId: "evt-11",
    type: "agent.decision",
    agentId: "skeptic",
    update: {
      summary: "Testing whether two stars fit better",
      inspector: {
        currentQuestion: "Can P/2 or 2P explain the signal better?",
        evidenceRefs: ["E14", "E17"],
        action: "harmonic_test",
        expectedDiscriminator: "consistency at P/2, P and 2P",
        model: "DeepSeek-V4 · demo trace",
        latency: "3.2 s · synthetic telemetry",
        schema: "valid",
      },
    },
    timestamp: t(22),
    holdMs: 2400,
    trace: {
      actor: "SKEPTIC",
      headline: "harmonic_test proposed",
      detail: "Cost 1 evidence unit",
      tone: "model",
    },
  },
  {
    eventId: "evt-12",
    type: "agent.handoff",
    from: "skeptic",
    to: "critic",
    kind: "model",
    timestamp: t(25),
    holdMs: 1300,
    view: { phase: "reviewing", stageIndex: 6, stageLabel: "Review test" },
    trace: {
      actor: "HANDOFF",
      headline: "Skeptic → Critic",
      detail: "Bounded experiment review",
      tone: "model",
    },
  },
  {
    eventId: "evt-13",
    type: "critic.review",
    verdict: "APPROVE",
    summary: "This check can separate the two explanations.",
    timestamp: t(27),
    holdMs: 2200,
    trace: {
      actor: "CRITIC",
      headline: "APPROVE",
      detail: "Budget valid · evidence dependency valid",
      tone: "approved",
    },
  },
  {
    eventId: "evt-14",
    type: "agent.handoff",
    from: "critic",
    to: "science-tool",
    kind: "science",
    timestamp: t(29),
    holdMs: 1300,
    trace: {
      actor: "HANDOFF",
      headline: "Critic → Science tool",
      detail: "Model proposal enters deterministic authority",
      tone: "science",
    },
  },
  {
    eventId: "evt-15",
    type: "tool.started",
    tool: { name: "harmonic_test", status: "running", authority: "deterministic" },
    budgetUsed: 1,
    timestamp: t(30),
    holdMs: 1800,
    view: {
      phase: "testing",
      stageIndex: 7,
      stageLabel: "Run check",
      currentQuestion: "Do half or double periods fit better?",
    },
    trace: {
      actor: "SCIENCE TOOL",
      headline: "harmonic_test running",
      detail: "Allowlisted · deterministic",
      tone: "science",
    },
  },
  {
    eventId: "evt-16",
    type: "tool.completed",
    tool: {
      name: "harmonic_test",
      status: "complete",
      durationMs: 420,
      evidenceRef: "E18",
      authority: "deterministic",
    },
    timestamp: t(32),
    holdMs: 2200,
    view: {
      instrument: instrument("harmonic", "Alternative periods", [
        { label: "P/2", value: "1.592 d" },
        { label: "P", value: "3.184 d", evidenceRef: "E14" },
        { label: "2P", value: "6.368 d" },
      ]),
    },
    trace: {
      actor: "SCIENCE TOOL",
      headline: "harmonic_test complete",
      detail: "420 ms · no stronger alias",
      tone: "science",
    },
  },
  {
    eventId: "evt-17",
    type: "evidence.appended",
    evidence: DEMO_EVIDENCE.E18,
    timestamp: t(33),
    holdMs: 1900,
    view: { stageIndex: 8, stageLabel: "Evidence added" },
    trace: {
      actor: "EVIDENCE",
      headline: "E18 appended",
      detail: "Harmonic diagnostic",
      tone: "science",
      evidenceRef: "E18",
    },
  },
  {
    eventId: "evt-18",
    type: "hypothesis.updated",
    hypothesisId: "eclipsing-binary",
    update: { state: "weakened", evidenceRefs: ["E18"], note: "No stronger harmonic dominance" },
    timestamp: t(35),
    holdMs: 2100,
    trace: {
      actor: "LEDGER",
      headline: "Binary alternative weakened",
      detail: "−E18 harmonic",
      tone: "science",
    },
  },
  {
    eventId: "evt-19",
    type: "agent.started",
    agentId: "director",
    timestamp: t(38),
    holdMs: 2200,
    view: {
      phase: "locking",
      stageIndex: 9,
      stageLabel: "Save result",
      currentQuestion: "Is there enough evidence to stop?",
      cameraPose: "lock",
    },
    trace: {
      actor: "DIRECTOR",
      headline: "Evidence sufficient",
      detail: "Stop condition reached",
      tone: "model",
    },
  },
  {
    eventId: "evt-20",
    type: "result.locked",
    hash: "8f21a70c6b2dd63b1e45297a6d5c41e4db348c7712f388da7c64a97b1ef7c19a",
    lockedAt: "2026-08-15T20:41:40Z",
    timestamp: t(40),
    holdMs: 2800,
    view: {
      phase: "locked",
      stageLabel: "Result saved",
      currentQuestion: "Result saved",
      cameraPose: "lock",
    },
    trace: {
      actor: "AUTHORITY",
      headline: "Measurements locked",
      detail: "SHA-256 receipt issued · ground truth sealed",
      tone: "unresolved",
    },
  },
]

export const DEMO_MODE_STEPS: Record<InstrumentMode, number> = {
  raw: 0,
  bls: 3,
  "phase-fold": 7,
  "odd-even": 8,
  secondary: 9,
  harmonic: 16,
}

export const DEMO_STAGE_MARKERS = [
  { label: "Observe", step: 0 },
  { label: "Detect", step: 4 },
  { label: "Measure", step: 7 },
  { label: "Challenge", step: 11 },
  { label: "Save", step: 20 },
] as const
