"use client"

import { useCallback, useEffect, useReducer, useRef, useState } from "react"

import {
  ClientError,
  createInvestigation,
  getInvestigationPlot,
  getMissionControl,
  listArtifacts,
  listTargets,
  listViewerTargets,
  resumeInvestigation,
} from "@/lib/api"
import type {
  ArtifactMetadata,
  InvestigationEvent,
  MissionControlSnapshot,
  PlotMode,
  TargetOption,
  ViewerTarget,
} from "@/lib/contracts"
import { subscribeToInvestigation } from "@/lib/events"

import type { InstrumentMode, InvestigationPresentationState } from "../model/presentation-state"
import {
  instrumentFromPlot,
  presentationFromSnapshot,
  unavailableInstrument,
} from "./backend-adapter"
import {
  appendEventTail,
  canAcceptSnapshot,
  INITIAL_PLAYBACK_STATE,
  livePlaybackReducer,
  plotEvidenceVersion,
  reconcileEventTail,
  shouldRequestPlot,
} from "./live-state"

const RUN_KEY = "exoswarm.live.run_id"
const MODE_KEY = "exoswarm.data_mode"
const IDEMPOTENCY_KEY = "exoswarm.live.start_key"

const ACTIVE_STATUSES = new Set([
  "INITIALIZED",
  "PREPARING",
  "SEARCHING",
  "VETTING_MANDATORY",
  "SELECTING_ADAPTIVE_EXPERIMENT",
  "WAITING_FOR_CRITIC",
  "RUNNING_TOOL",
  "UPDATING_EVIDENCE",
  "FINALIZING",
])

const EMPTY_STATE: InvestigationPresentationState = {
  run: { id: "pending", mode: "live", status: "INITIALIZED", terminalReason: null },
  target: { id: "No target selected", sector: "Sealed observation", dataLabel: "API investigation", groundTruthState: "sealed" },
  phase: "observing",
  stageIndex: 1,
  stageLabel: "Select target",
  currentQuestion: "Choose an observation to begin",
  agents: [
    ["director", "Director", "Orchestrates bounded checks"],
    ["observer", "Observer", "Checks data quality"],
    ["signal", "Signal", "Finds repeats"],
    ["transit_hunter", "Transit", "Measures the dips"],
    ["skeptic", "Skeptic", "Tests other causes"],
    ["critic", "Critic", "Approves safe checks"],
  ].map(([id, label, role]) => ({
    id: id as InvestigationPresentationState["agents"][number]["id"],
    label,
    function: role,
    status: "waiting" as const,
    summary: "Idle",
    inspector: {
      currentQuestion: "No active question",
      evidenceRefs: [],
      action: "none",
      expectedDiscriminator: "not selected",
      model: "not measured",
      latency: "not measured",
      schema: "pending" as const,
    },
  })),
  hypotheses: [],
  evidence: [],
  instrument: unavailableInstrument("raw", "Start an investigation to load measured evidence."),
  evidenceBudget: { used: 0, total: 0 },
  cameraPose: "field",
  timeline: [],
}

function clientError(error: unknown, runId?: string): ClientError {
  if (error instanceof ClientError) return error
  return new ClientError({
    code: error instanceof DOMException && error.name === "AbortError" ? "REQUEST_ABORTED" : "CLIENT_FAILURE",
    message: error instanceof Error ? error.message : "The live investigation request failed",
    run_id: runId ?? null,
    recoverable: true,
  })
}

export function useLiveInvestigation(enabled: boolean) {
  const [targets, setTargets] = useState<TargetOption[]>([])
  const [viewerTargets, setViewerTargets] = useState<ViewerTarget[]>([])
  const [targetsLoading, setTargetsLoading] = useState(enabled)
  const [runId, setRunId] = useState<string>()
  const [playback, dispatchPlayback] = useReducer(livePlaybackReducer, INITIAL_PLAYBACK_STATE)
  const [error, setError] = useState<ClientError | null>(null)
  const [artifacts, setArtifacts] = useState<ArtifactMetadata[]>([])
  const [selectedMode, setSelectedMode] = useState<InstrumentMode>("raw")
  const [plots, setPlots] = useState<Record<string, InvestigationPresentationState["instrument"]>>({})
  const abortRef = useRef(new AbortController())
  const closeSourceRef = useRef<(() => void) | undefined>(undefined)
  const startPromiseRef = useRef<Promise<void> | null>(null)
  const acceptedSequenceRef = useRef(0)
  const streamSequenceRef = useRef(0)
  const eventBufferRef = useRef<InvestigationEvent[]>([])
  const attemptedPlotsRef = useRef(new Set<string>())
  const loadedPlotsRef = useRef(new Set<string>())
  const inFlightPlotsRef = useRef(new Set<string>())
  const plotVersionRef = useRef<Partial<Record<InstrumentMode, string>>>({})
  const reconcileQueueRef = useRef(Promise.resolve())
  const reconnectTimerRef = useRef<number | undefined>(undefined)
  const snapshotRef = useRef<MissionControlSnapshot | undefined>(undefined)
  const runIdRef = useRef<string | undefined>(undefined)
  const generationRef = useRef(0)

  const acceptSnapshot = useCallback((nextSnapshot: MissionControlSnapshot, activeRunId: string, generation: number) => {
    if (generation !== generationRef.current) return false
    if (!canAcceptSnapshot(nextSnapshot, activeRunId, acceptedSequenceRef.current)) return false
    eventBufferRef.current = reconcileEventTail(eventBufferRef.current, nextSnapshot)
    acceptedSequenceRef.current = nextSnapshot.last_sequence
    streamSequenceRef.current = Math.max(
      nextSnapshot.last_sequence,
      ...eventBufferRef.current.map((event) => event.sequence),
    )
    snapshotRef.current = nextSnapshot
    dispatchPlayback({
      type: "accept",
      snapshot: nextSnapshot,
      presentation: presentationFromSnapshot(nextSnapshot),
    })
    if (!ACTIVE_STATUSES.has(nextSnapshot.status)) {
      closeSourceRef.current?.()
      closeSourceRef.current = undefined
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
    }
    return true
  }, [])

  const reconcile = useCallback((activeRunId: string, generation = generationRef.current) => {
    const operation = reconcileQueueRef.current.then(async () => {
      if (generation !== generationRef.current || runIdRef.current !== activeRunId) return undefined
      const nextSnapshot = await getMissionControl(activeRunId, abortRef.current.signal)
      return acceptSnapshot(nextSnapshot, activeRunId, generation) ? nextSnapshot : undefined
    })
    reconcileQueueRef.current = operation.then(() => undefined, () => undefined)
    return operation
  }, [acceptSnapshot])

  const initializeRun = useCallback((activeRunId: string) => {
    generationRef.current += 1
    abortRef.current.abort()
    abortRef.current = new AbortController()
    closeSourceRef.current?.()
    closeSourceRef.current = undefined
    if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
    runIdRef.current = activeRunId
    acceptedSequenceRef.current = 0
    streamSequenceRef.current = 0
    eventBufferRef.current = []
    attemptedPlotsRef.current.clear()
    loadedPlotsRef.current.clear()
    inFlightPlotsRef.current.clear()
    plotVersionRef.current = {}
    reconcileQueueRef.current = Promise.resolve()
    dispatchPlayback({ type: "reset" })
    setArtifacts([])
    setPlots({})
    return generationRef.current
  }, [])

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    Promise.all([listTargets(controller.signal), listViewerTargets(controller.signal)])
      .then(([safeTargets, catalogTargets]) => {
        setTargets(safeTargets)
        setViewerTargets(catalogTargets)
        setTargetsLoading(false)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(clientError(reason))
        setTargetsLoading(false)
      })
    return () => controller.abort()
  }, [enabled])

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return
    const storedRunId = window.sessionStorage.getItem(RUN_KEY)
    const storedMode = window.sessionStorage.getItem(MODE_KEY)
    if (!storedRunId || storedMode !== "live") return
    let restoreGeneration: number | undefined
    const restoreTimer = window.setTimeout(() => {
      const generation = initializeRun(storedRunId)
      restoreGeneration = generation
      reconcile(storedRunId, generation)
        .then(async (restored) => {
          if (!restored || generation !== generationRef.current) return
          setRunId(storedRunId)
          if (!ACTIVE_STATUSES.has(restored.status)) {
            const listed = await listArtifacts(storedRunId, abortRef.current.signal)
            if (generation === generationRef.current) setArtifacts(listed.artifacts)
          }
          if (ACTIVE_STATUSES.has(restored.status) && !restored.execution.active) {
            await resumeInvestigation(storedRunId, abortRef.current.signal)
            await reconcile(storedRunId, generation)
          }
        })
        .catch((reason: unknown) => {
          if (generation === generationRef.current && !abortRef.current.signal.aborted) setError(clientError(reason, storedRunId))
        })
    }, 0)
    return () => {
      window.clearTimeout(restoreTimer)
      if (restoreGeneration === generationRef.current) {
        generationRef.current += 1
        abortRef.current.abort()
        closeSourceRef.current?.()
        closeSourceRef.current = undefined
      }
    }
  }, [enabled, initializeRun, reconcile])

  useEffect(() => {
    if (!enabled || !runId) return
    let disposed = false
    const effectGeneration = generationRef.current

    const connect = () => {
      if (disposed || effectGeneration !== generationRef.current) return
      const current = snapshotRef.current
      if (!current || current.run_id !== runId || !ACTIVE_STATUSES.has(current.status)) return
      closeSourceRef.current?.()
      closeSourceRef.current = subscribeToInvestigation(runId, {
        afterSequence: Math.max(acceptedSequenceRef.current, streamSequenceRef.current),
        onOpen: () => setError(null),
        onEvent: (event: InvestigationEvent) => {
          if (event.run_id !== runId || effectGeneration !== generationRef.current) return
          const tail = appendEventTail(eventBufferRef.current, event, acceptedSequenceRef.current)
          if (tail === eventBufferRef.current) return
          eventBufferRef.current = tail
          streamSequenceRef.current = Math.max(streamSequenceRef.current, event.sequence)
          const generation = generationRef.current
          void reconcile(runId, generation)
            .catch((reason: unknown) => {
              if (generation === generationRef.current && !abortRef.current.signal.aborted) setError(clientError(reason, runId))
            })
        },
        onError: () => {
          if (effectGeneration !== generationRef.current) return
          closeSourceRef.current?.()
          closeSourceRef.current = undefined
          const generation = generationRef.current
          reconcile(runId, generation)
            .then((reconciled) => {
              if (disposed || generation !== generationRef.current) return
              const current = reconciled ?? snapshotRef.current
              if (!current || !ACTIVE_STATUSES.has(current.status)) return
              reconnectTimerRef.current = window.setTimeout(connect, 500)
            })
            .catch((reason: unknown) => {
              if (generation !== generationRef.current || abortRef.current.signal.aborted) return
              setError(clientError(reason, runId))
              reconnectTimerRef.current = window.setTimeout(connect, 500)
            })
        },
      })
    }

    connect()
    return () => {
      disposed = true
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
      closeSourceRef.current?.()
      closeSourceRef.current = undefined
    }
  }, [enabled, reconcile, runId])

  useEffect(() => {
    const currentSnapshot = playback.snapshot
    if (!enabled || !runId || !currentSnapshot || !shouldRequestPlot(currentSnapshot, selectedMode)) return
    const version = plotEvidenceVersion(currentSnapshot, selectedMode as PlotMode)
    if (loadedPlotsRef.current.has(version) || attemptedPlotsRef.current.has(version) || inFlightPlotsRef.current.has(version)) return
    attemptedPlotsRef.current.add(version)
    inFlightPlotsRef.current.add(version)
    plotVersionRef.current[selectedMode] = version
    const generation = generationRef.current
    getInvestigationPlot(runId, selectedMode as PlotMode, abortRef.current.signal)
      .then((plot) => {
        if (generation !== generationRef.current || plotVersionRef.current[selectedMode] !== version) return
        if (plot.available) loadedPlotsRef.current.add(version)
        setPlots((current) => ({ ...current, [version]: instrumentFromPlot(plot) }))
      })
      .catch((reason: unknown) => {
        if (generation !== generationRef.current || abortRef.current.signal.aborted) return
        const failure = clientError(reason, runId)
        setError(failure)
        setPlots((current) => ({ ...current, [version]: unavailableInstrument(selectedMode, failure.message) }))
      })
      .finally(() => inFlightPlotsRef.current.delete(version))
  }, [enabled, playback.snapshot, runId, selectedMode])

  const start = (targetId: string): Promise<void> => {
    if (!enabled) return Promise.resolve()
    if (startPromiseRef.current) return startPromiseRef.current
    const operation = (async () => {
      setError(null)
      const controller = abortRef.current
      let operationGeneration = generationRef.current
      let key = window.sessionStorage.getItem(IDEMPOTENCY_KEY)
      if (!key) {
        key = globalThis.crypto.randomUUID()
        window.sessionStorage.setItem(IDEMPOTENCY_KEY, key)
      }
      try {
        const created = await createInvestigation(targetId, key, controller.signal)
        const generation = initializeRun(created.run_id)
        operationGeneration = generation
        window.sessionStorage.setItem(RUN_KEY, created.run_id)
        window.sessionStorage.setItem(MODE_KEY, "live")
        const initial = await reconcile(created.run_id, generation)
        if (!initial) throw new Error("The initial investigation snapshot was not accepted")
        setRunId(created.run_id)
        window.sessionStorage.removeItem(IDEMPOTENCY_KEY)
      } catch (reason) {
        if (operationGeneration === generationRef.current && !abortRef.current.signal.aborted) {
          setError(clientError(reason))
        }
        throw reason
      }
    })()
    startPromiseRef.current = operation.finally(() => {
      startPromiseRef.current = null
    })
    return startPromiseRef.current
  }

  const resume = async (requestedRunId: string) => {
    setError(null)
    const generation = initializeRun(requestedRunId)
    await resumeInvestigation(requestedRunId, abortRef.current.signal)
    window.sessionStorage.setItem(RUN_KEY, requestedRunId)
    window.sessionStorage.setItem(MODE_KEY, "live")
    const restored = await reconcile(requestedRunId, generation)
    if (restored) setRunId(requestedRunId)
  }

  const setStep = (value: number) => {
    dispatchPlayback({ type: "step", step: value })
  }

  const setPlaying = (value: boolean) => {
    dispatchPlayback({ type: "following", following: value })
  }

  const replay = () => {
    dispatchPlayback({ type: "replay" })
  }

  const selectInstrumentMode = (mode: InstrumentMode) => {
    setSelectedMode(mode)
  }

  const reset = () => {
    closeSourceRef.current?.()
    closeSourceRef.current = undefined
    generationRef.current += 1
    runIdRef.current = undefined
    abortRef.current.abort()
    abortRef.current = new AbortController()
    if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
    window.sessionStorage.removeItem(RUN_KEY)
    window.sessionStorage.removeItem(IDEMPOTENCY_KEY)
    setRunId(undefined)
    snapshotRef.current = undefined
    dispatchPlayback({ type: "reset" })
    setError(null)
    setArtifacts([])
    setPlots({})
    acceptedSequenceRef.current = 0
    streamSequenceRef.current = 0
    eventBufferRef.current = []
    attemptedPlotsRef.current.clear()
    loadedPlotsRef.current.clear()
    inFlightPlotsRef.current.clear()
    plotVersionRef.current = {}
    reconcileQueueRef.current = Promise.resolve()
  }

  const history = playback.history
  const state = history[playback.step]?.presentation ?? history.at(-1)?.presentation ?? EMPTY_STATE
  const selectedPlotVersion = playback.snapshot && shouldRequestPlot(playback.snapshot, selectedMode)
    ? plotEvidenceVersion(playback.snapshot, selectedMode)
    : undefined
  const selectedInstrument = (selectedPlotVersion ? plots[selectedPlotVersion] : undefined)
    ?? (state.instrument.mode === selectedMode
      ? state.instrument
      : unavailableInstrument(selectedMode, "This backend measurement is not available for the current evidence."))
  return {
    mode: "live" as const,
    targets,
    viewerTargets,
    targetsLoading,
    runId,
    snapshot: playback.snapshot,
    state,
    instrument: selectedInstrument,
    step: playback.step,
    totalSteps: Math.max(0, history.length - 1),
    isPlaying: playback.following,
    error,
    artifacts,
    start,
    resume,
    setPlaying,
    setStep,
    replay,
    selectInstrumentMode,
    reset,
  }
}
